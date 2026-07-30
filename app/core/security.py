from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Any

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, password_hash_value: str) -> bool:
    try:
        return password_hash.verify(password, password_hash_value)
    except Exception:
        return False


def _encode_access_token(payload: dict[str, Any]) -> tuple[str, int]:
    expires_minutes = settings.access_token_minutes
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=expires_minutes)
    payload = {
        **payload,
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_minutes * 60


def create_access_token(
    *,
    user_id: int,
    empresa_id: int,
    cargo: str,
) -> tuple[str, int]:
    return _encode_access_token(
        {
            "sub": str(user_id),
            "empresa_id": empresa_id,
            "cargo": cargo,
            "kind": "company_user",
        }
    )


def create_super_admin_access_token(*, super_admin_id: int) -> tuple[str, int]:
    return _encode_access_token(
        {
            "sub": str(super_admin_id),
            "kind": "super_admin",
        }
    )


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except InvalidTokenError as exc:
        raise ValueError("Token inválido ou expirado.") from exc


def create_password_reset_token() -> tuple[str, str]:
    raw_token = secrets.token_urlsafe(48)
    return raw_token, hash_password_reset_token(raw_token)


def hash_password_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
