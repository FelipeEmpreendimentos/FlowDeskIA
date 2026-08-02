from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database.database import get_db
from app.models.enums import CargoUsuario
from app.models.models import Empresa, Usuario
from app.models.platform import EmpresaPlataforma
from app.services.access_control import user_module_access

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
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
            "Usuário inválido ou inativo.",
        )

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

    return user


def require_roles(
    *roles: CargoUsuario,
) -> Callable[[Usuario], Usuario]:
    def dependency(
        current_user: Usuario = Depends(get_current_user),
    ) -> Usuario:
        if current_user.cargo not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Você não possui permissão para esta operação.",
            )
        return current_user

    return dependency


def require_roles_or_module(
    module: str,
    *roles: CargoUsuario,
) -> Callable[[Usuario], Usuario]:
    def dependency(
        current_user: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> Usuario:
        if current_user.cargo in roles or user_module_access(db, current_user, module):
            return current_user
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Você não possui permissão para acessar este módulo.",
        )

    return dependency
