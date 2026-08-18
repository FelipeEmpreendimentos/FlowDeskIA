from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import PRODUCTION_ENVIRONMENTS, settings
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    hash_password_reset_token,
    verify_password,
)
from app.database.database import get_db
from app.models.models import Empresa, PasswordResetToken, Usuario
from app.models.platform import EmpresaPlataforma
from app.schemas.auth import (
    AlterarSenhaRequest,
    LoginRequest,
    RecuperarSenhaRequest,
    RecuperarSenhaResponse,
    RedefinirSenhaRequest,
    TokenResponse,
    UsuarioLogado,
)
from app.schemas.common import MessageResponse
from app.services.attendance_presence import STATUS_DISPONIVEL, set_presence_status
from app.services.email import send_password_reset_email

router = APIRouter(prefix="/auth", tags=["Autenticação"])

REFRESH_COOKIE_NAME = "flowdesk_refresh_token"
REFRESH_TOKEN_DAYS = 30
REFRESH_COOKIE_PATH = "/api/v1/auth"


def _cookie_seguro() -> bool:
    return settings.environment in PRODUCTION_ENVIRONMENTS


def _definir_cookie_lembrado(
    response: Response,
    *,
    user_id: int,
    empresa_id: int,
) -> None:
    refresh_token, max_age = create_refresh_token(
        user_id=user_id,
        empresa_id=empresa_id,
        days=REFRESH_TOKEN_DAYS,
    )
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=max_age,
        httponly=True,
        secure=_cookie_seguro(),
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )


def _remover_cookie_lembrado(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        secure=_cookie_seguro(),
        httponly=True,
        samesite="lax",
    )


def _validar_acesso_empresa(db: Session, empresa_id: int) -> None:
    empresa = db.scalar(
        select(Empresa).where(
            Empresa.id == empresa_id,
            Empresa.ativo.is_(True),
        )
    )
    if empresa is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "A empresa está inativa. Entre em contato com o suporte.",
        )

    try:
        plataforma = db.get(EmpresaPlataforma, empresa_id)
    except ProgrammingError:
        db.rollback()
        plataforma = None

    if plataforma and plataforma.status in {"SUSPENSA", "CANCELADA", "ARQUIVADA"}:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "O acesso da empresa está suspenso. Entre em contato com o suporte.",
        )


def _buscar_usuario_ativo(
    db: Session,
    *,
    user_id: int,
    empresa_id: int,
) -> Usuario:
    user = db.scalar(
        select(Usuario).where(
            Usuario.id == user_id,
            Usuario.empresa_id == empresa_id,
            Usuario.ativo.is_(True),
        )
    )
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "A sessão não é mais válida.",
        )
    _validar_acesso_empresa(db, empresa_id)
    return user


@router.post("/login", response_model=TokenResponse)
def login(
    data: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = db.scalar(
        select(Usuario).where(
            Usuario.empresa_id == data.empresa_id,
            func.lower(Usuario.email) == data.email.strip().lower(),
            Usuario.ativo.is_(True),
        )
    )

    if user is None or not verify_password(data.senha, user.senha_hash):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Empresa, e-mail ou senha inválidos.",
        )

    _validar_acesso_empresa(db, user.empresa_id)
    user.ultimo_login = datetime.now(timezone.utc)
    db.commit()
    set_presence_status(db, user, STATUS_DISPONIVEL)

    token, expires_in = create_access_token(
        user_id=user.id,
        empresa_id=user.empresa_id,
        cargo=user.cargo.value,
    )

    if data.manter_conectado:
        _definir_cookie_lembrado(
            response,
            user_id=user.id,
            empresa_id=user.empresa_id,
        )
    else:
        _remover_cookie_lembrado(response)

    return TokenResponse(access_token=token, expires_in=expires_in)


@router.post("/refresh", response_model=TokenResponse)
def renovar_sessao(
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Não existe uma sessão lembrada neste dispositivo.",
        )

    try:
        payload = decode_access_token(refresh_token)
        if payload.get("kind") != "company_refresh":
            raise ValueError
        user_id = int(payload["sub"])
        empresa_id = int(payload["empresa_id"])
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "A sessão lembrada expirou ou é inválida.",
        ) from exc

    user = _buscar_usuario_ativo(
        db,
        user_id=user_id,
        empresa_id=empresa_id,
    )
    token, expires_in = create_access_token(
        user_id=user.id,
        empresa_id=user.empresa_id,
        cargo=user.cargo.value,
    )
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    _remover_cookie_lembrado(response)


@router.get("/me", response_model=UsuarioLogado)
def me(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    return current_user


@router.post("/alterar-senha", response_model=MessageResponse)
def alterar_senha(
    data: AlterarSenhaRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    if not verify_password(data.senha_atual, current_user.senha_hash):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Senha atual inválida.",
        )
    current_user.senha_hash = hash_password(data.nova_senha)
    db.commit()
    return MessageResponse(message="Senha alterada com sucesso.")


@router.post("/recuperar-senha", response_model=RecuperarSenhaResponse)
def recuperar_senha(
    data: RecuperarSenhaRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> RecuperarSenhaResponse:
    email = data.email.strip().lower()
    generic_message = (
        "Se os dados estiverem corretos, você receberá instruções para redefinir a senha."
    )

    user = db.scalar(
        select(Usuario).where(
            Usuario.empresa_id == data.empresa_id,
            func.lower(Usuario.email) == email,
            Usuario.ativo.is_(True),
        )
    )
    if user is None:
        return RecuperarSenhaResponse(message=generic_message)

    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.usuario_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=datetime.now(timezone.utc))
    )

    raw_token = create_password_reset_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
    reset_token = PasswordResetToken(
        usuario_id=user.id,
        token_hash=hash_password_reset_token(raw_token),
        expires_at=expires_at,
    )
    db.add(reset_token)
    db.commit()

    reset_url = f"{settings.frontend_url.rstrip('/')}/redefinir-senha?token={raw_token}"
    email_sent = send_password_reset_email(
        recipient=user.email,
        user_name=user.nome,
        reset_url=reset_url,
    )

    development_url = None
    if settings.environment not in PRODUCTION_ENVIRONMENTS and not email_sent:
        development_url = reset_url

    return RecuperarSenhaResponse(
        message=generic_message,
        development_reset_url=development_url,
    )


@router.post("/redefinir-senha", response_model=MessageResponse)
def redefinir_senha(
    data: RedefinirSenhaRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    token_hash = hash_password_reset_token(data.token)
    reset_token = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
        )
    )
    if reset_token is None or reset_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Link de redefinição inválido ou expirado.",
        )

    user = db.get(Usuario, reset_token.usuario_id)
    if user is None or not user.ativo:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Usuário não está mais disponível.",
        )

    user.senha_hash = hash_password(data.nova_senha)
    reset_token.used_at = datetime.now(timezone.utc)
    db.commit()
    return MessageResponse(message="Senha redefinida com sucesso.")
