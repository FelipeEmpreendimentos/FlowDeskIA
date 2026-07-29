from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    hash_password,
    hash_password_reset_token,
    verify_password,
)
from app.database.database import get_db
from app.models.models import PasswordResetToken, Usuario
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
from app.services.email import send_password_reset_email

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
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

    user.ultimo_login = datetime.now(timezone.utc)
    db.commit()

    token, expires_in = create_access_token(
        user_id=user.id,
        empresa_id=user.empresa_id,
        cargo=user.cargo.value,
    )

    return TokenResponse(access_token=token, expires_in=expires_in)


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
            "A senha atual está incorreta.",
        )

    current_user.senha_hash = hash_password(data.nova_senha)
    db.commit()
    return MessageResponse(mensagem="Senha alterada com sucesso.")


@router.post("/recuperar-senha", response_model=RecuperarSenhaResponse)
def recuperar_senha(
    data: RecuperarSenhaRequest,
    db: Session = Depends(get_db),
) -> RecuperarSenhaResponse:
    generic_message = (
        "Se os dados informados estiverem cadastrados, você receberá um "
        "e-mail com o link para redefinir sua senha. Verifique também a "
        "caixa de spam."
    )

    # Não permite que o sistema finja ter enviado uma mensagem quando o
    # serviço de e-mail ainda não foi configurado.
    if not settings.smtp_configured:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "O serviço de recuperação por e-mail ainda não está configurado.",
        )

    user = db.scalar(
        select(Usuario).where(
            Usuario.empresa_id == data.empresa_id,
            func.lower(Usuario.email) == data.email.strip().lower(),
            Usuario.ativo.is_(True),
        )
    )

    # A resposta é intencionalmente igual para contas existentes e
    # inexistentes, evitando revelar quais e-mails estão cadastrados.
    if user is None:
        return RecuperarSenhaResponse(mensagem=generic_message)

    now = datetime.now(timezone.utc)
    cooldown_start = now - timedelta(
        seconds=settings.reset_request_cooldown_seconds
    )
    recent_request = db.scalar(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.usuario_id == user.id,
            PasswordResetToken.created_at >= cooldown_start,
        )
        .order_by(PasswordResetToken.created_at.desc())
        .limit(1)
    )

    # Evita vários e-mails seguidos para a mesma conta.
    if recent_request is not None:
        return RecuperarSenhaResponse(mensagem=generic_message)

    raw_token, token_hash = create_password_reset_token()
    reset_token = PasswordResetToken(
        usuario_id=user.id,
        token_hash=token_hash,
        expires_at=now + timedelta(minutes=settings.reset_token_minutes),
    )
    db.add(reset_token)
    db.commit()
    db.refresh(reset_token)

    reset_url = f"{settings.frontend_url}/redefinir-senha?token={raw_token}"
    email_sent = send_password_reset_email(
        recipient=user.email,
        reset_url=reset_url,
    )

    if not email_sent:
        # O token que não chegou ao destinatário não deve continuar válido.
        db.delete(reset_token)
        db.commit()
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Não foi possível enviar o e-mail de recuperação agora. "
            "Tente novamente em alguns minutos.",
        )

    # Depois do envio bem-sucedido, invalida os links anteriores.
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.usuario_id == user.id,
            PasswordResetToken.id != reset_token.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    db.commit()

    return RecuperarSenhaResponse(mensagem=generic_message)


@router.post("/redefinir-senha", response_model=MessageResponse)
def redefinir_senha(
    data: RedefinirSenhaRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    now = datetime.now(timezone.utc)
    token_hash = hash_password_reset_token(data.token)

    reset_token = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
    )

    if reset_token is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "O link de recuperação é inválido ou expirou.",
        )

    user = db.scalar(
        select(Usuario).where(
            Usuario.id == reset_token.usuario_id,
            Usuario.ativo.is_(True),
        )
    )

    if user is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "O link de recuperação é inválido ou expirou.",
        )

    user.senha_hash = hash_password(data.nova_senha)
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.usuario_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    db.commit()

    return MessageResponse(mensagem="Senha redefinida com sucesso.")
