from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database.database import get_db
from app.models.platform import SuperAdmin

super_admin_bearer = HTTPBearer(auto_error=False)


def get_current_super_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(super_admin_bearer),
    db: Session = Depends(get_db),
) -> SuperAdmin:
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Autenticação de Super Admin necessária.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
        if payload.get("kind") != "super_admin":
            raise ValueError
        super_admin_id = int(payload["sub"])
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Token de Super Admin inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    super_admin = db.scalar(
        select(SuperAdmin).where(
            SuperAdmin.id == super_admin_id,
            SuperAdmin.ativo.is_(True),
        )
    )
    if super_admin is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Conta de Super Admin inválida ou inativa.",
        )
    return super_admin
