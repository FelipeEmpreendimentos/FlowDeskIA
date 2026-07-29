from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database.database import get_db
from app.models.enums import CargoUsuario
from app.models.models import Usuario

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
