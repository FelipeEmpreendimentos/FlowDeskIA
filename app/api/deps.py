from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import InvalidRequestError, ProgrammingError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.core.security import decode_access_token
from app.database.database import get_db
from app.models.enums import CargoUsuario
from app.models.models import Empresa, Usuario
from app.models.platform import EmpresaPlataforma
from app.services.access_control import user_module_access, user_module_manage
from app.services.appointment_retention import auto_cancel_stale_appointments

bearer_scheme = HTTPBearer(auto_error=False)

ROLE_PERMISSION_PATHS = {
    "/api/v1/agendamentos": "AGENDA",
    "/api/v1/chat-interno": "CHAT_INTERNO",
    "/api/v1/conversas": "CONVERSAS",
    "/api/v1/clientes": "CLIENTES",
    "/api/v1/veiculos": "VEICULOS",
    "/api/v1/servicos": "SERVICOS",
    "/api/v1/financeiro": "FINANCEIRO",
    "/api/v1/relatorios": "RELATORIOS",
    "/api/v1/usuarios": "EQUIPE",
    "/api/v1/horarios": "EQUIPE",
    "/api/v1/bloqueios-agenda": "EQUIPE",
}

READ_METHODS = {"GET", "HEAD", "OPTIONS"}


def _module_for_request(request: Request) -> str | None:
    path = request.url.path.rstrip("/") or "/"
    for prefix, module in ROLE_PERMISSION_PATHS.items():
        if path == prefix or path.startswith(f"{prefix}/"):
            return module
    return None


def _load_user_context(
    db: Session,
    *,
    user_id: int,
    empresa_id: int,
) -> tuple[Usuario | None, Empresa | None, EmpresaPlataforma | None]:
    """Carrega usuário, empresa e estado da plataforma em um único round trip.

    O fallback mantém compatibilidade com bancos locais antigos que ainda não
    possuam a tabela empresa_plataforma.
    """
    try:
        row = db.execute(
            select(Usuario, Empresa, EmpresaPlataforma)
            .join(Empresa, Empresa.id == Usuario.empresa_id)
            .outerjoin(
                EmpresaPlataforma,
                EmpresaPlataforma.empresa_id == Empresa.id,
            )
            .where(
                Usuario.id == user_id,
                Usuario.empresa_id == empresa_id,
                Usuario.ativo.is_(True),
            )
        ).one_or_none()
        if row is None:
            return None, None, None
        user, empresa, plataforma = row
        return user, empresa, plataforma
    except ProgrammingError:
        db.rollback()
        user = db.scalar(
            select(Usuario).where(
                Usuario.id == user_id,
                Usuario.empresa_id == empresa_id,
                Usuario.ativo.is_(True),
            )
        )
        if user is None:
            return None, None, None
        empresa = db.scalar(select(Empresa).where(Empresa.id == empresa_id))
        return user, empresa, None


def _reuse_middleware_context(
    request: Request,
    db: Session,
    *,
    user_id: int,
    empresa_id: int,
) -> tuple[Usuario, bool, str, str | None] | None:
    """Reaproveita o contexto já validado pelo middleware sem novo SELECT.

    O middleware usa uma sessão curta própria e entrega um objeto limpo e
    detached. ``merge(load=False)`` o anexa à sessão da rota sem consultar o
    Postgres novamente, preservando a possibilidade de a rota alterar o ORM.
    """
    snapshot = getattr(request.state, "flowdesk_auth_context", None)
    if not isinstance(snapshot, dict):
        return None
    if snapshot.get("user_id") != user_id or snapshot.get("empresa_id") != empresa_id:
        return None

    detached_user = snapshot.get("user")
    if not isinstance(detached_user, Usuario):
        return None

    try:
        user = db.merge(detached_user, load=False)
    except InvalidRequestError:
        return None

    return (
        user,
        bool(snapshot.get("empresa_ativo", False)),
        str(snapshot.get("empresa_timezone") or "America/Sao_Paulo"),
        snapshot.get("plataforma_status"),
    )


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Autenticação necessária.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
        if payload.get("kind", "company_user") != "company_user":
            raise ValueError
        user_id = int(payload["sub"])
        empresa_id = int(payload["empresa_id"])
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    reused = _reuse_middleware_context(
        request,
        db,
        user_id=user_id,
        empresa_id=empresa_id,
    )

    if reused is not None:
        user, empresa_ativa, empresa_timezone, plataforma_status = reused
    else:
        user, empresa, plataforma = _load_user_context(
            db,
            user_id=user_id,
            empresa_id=empresa_id,
        )
        if user is None:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Usuário inválido ou inativo.",
            )
        empresa_ativa = bool(empresa and empresa.ativo)
        empresa_timezone = (
            empresa.timezone if empresa is not None else "America/Sao_Paulo"
        )
        plataforma_status = plataforma.status if plataforma is not None else None

    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Usuário inválido ou inativo.",
        )

    if not empresa_ativa:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "A empresa está inativa. Entre em contato com o suporte.",
        )

    if plataforma_status in {"SUSPENSA", "CANCELADA", "ARQUIVADA"}:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "O acesso da empresa está suspenso. Entre em contato com o suporte.",
        )

    auto_cancel_stale_appointments(
        db,
        empresa_id=empresa_id,
        timezone_name=empresa_timezone,
    )

    module = _module_for_request(request)
    if (
        module
        and user.cargo == CargoUsuario.FUNCIONARIO
        and user_module_manage(db, user, module)
    ):
        # Elevação apenas durante a requisição para operações autorizadas.
        set_committed_value(user, "cargo", CargoUsuario.GERENTE)

    return user


def require_roles(
    *roles: CargoUsuario,
) -> Callable[[Usuario], Usuario]:
    def dependency(
        request: Request,
        current_user: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> Usuario:
        if current_user.cargo in roles:
            return current_user

        module = _module_for_request(request)
        if module:
            if request.method in READ_METHODS and user_module_access(
                db, current_user, module
            ):
                return current_user
            if user_module_manage(db, current_user, module):
                return current_user

        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Você não possui permissão para esta operação.",
        )

    return dependency


def require_roles_or_module(
    module: str,
    *roles: CargoUsuario,
) -> Callable[[Usuario], Usuario]:
    def dependency(
        request: Request,
        current_user: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> Usuario:
        if current_user.cargo in roles:
            return current_user
        if request.method in READ_METHODS and user_module_access(
            db, current_user, module
        ):
            return current_user
        if user_module_manage(db, current_user, module):
            return current_user
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Você não possui permissão para acessar este módulo.",
        )

    return dependency
