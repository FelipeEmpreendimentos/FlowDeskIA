from collections.abc import Awaitable, Callable

from fastapi import HTTPException
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.security import decode_access_token
from app.database.database import SessionLocal
from app.models.models import Usuario
from app.services.access_control import require_module_access, require_module_manage
from app.services.plans import enforce_limit, require_feature

FEATURE_PATHS = {
    "/api/v1/agendamentos": "AGENDA",
    "/api/v1/clientes": "CLIENTES",
    "/api/v1/veiculos": "VEICULOS",
    "/api/v1/servicos": "SERVICOS",
    "/api/v1/conversas": "CONVERSAS",
    "/api/v1/notificacoes": "NOTIFICACOES",
}

MODULE_PATHS = {
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

CREATE_LIMITS = {
    "/api/v1/agendamentos": "agendamentos_mes",
    "/api/v1/conversas": "conversas_mes",
    "/api/v1/configuracoes/integracoes": "canais",
}

READ_METHODS = {"GET", "HEAD", "OPTIONS"}

MANAGEMENT_EXACT_PATHS = {
    ("POST", "/api/v1/chat-interno/grupos"): "CHAT_INTERNO",
    ("POST", "/api/v1/conversas"): "CONVERSAS",
}

MANAGEMENT_MUTATION_PATHS = {
    "/api/v1/clientes": "CLIENTES",
    "/api/v1/veiculos": "VEICULOS",
    "/api/v1/servicos": "SERVICOS",
    "/api/v1/usuarios": "EQUIPE",
    "/api/v1/horarios": "EQUIPE",
    "/api/v1/bloqueios-agenda": "EQUIPE",
}


def _identity_from_request(request: Request) -> tuple[int, int] | None:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    try:
        payload = decode_access_token(token)
        if payload.get("kind", "company_user") != "company_user":
            return None
        return int(payload["sub"]), int(payload["empresa_id"])
    except (ValueError, KeyError, TypeError):
        return None


def _value_for_path(path: str, mapping: dict[str, str]) -> str | None:
    for prefix, value in mapping.items():
        if path == prefix or path.startswith(f"{prefix}/"):
            return value
    return None


def _management_module(method: str, path: str) -> str | None:
    exact = MANAGEMENT_EXACT_PATHS.get((method, path))
    if exact:
        return exact
    if method in READ_METHODS:
        return None
    return _value_for_path(path, MANAGEMENT_MUTATION_PATHS)


async def plan_access_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    identity = _identity_from_request(request)
    if identity is None:
        return await call_next(request)

    user_id, empresa_id = identity
    path = request.url.path.rstrip("/") or "/"
    feature = _value_for_path(path, FEATURE_PATHS)
    module = _value_for_path(path, MODULE_PATHS)
    management_module = _management_module(request.method, path)
    limit_key = CREATE_LIMITS.get(path) if request.method == "POST" else None

    if (
        feature is None
        and module is None
        and management_module is None
        and limit_key is None
    ):
        return await call_next(request)

    db = SessionLocal()
    try:
        user = db.scalar(
            select(Usuario).where(
                Usuario.id == user_id,
                Usuario.empresa_id == empresa_id,
                Usuario.ativo.is_(True),
            )
        )
        if user is not None and module:
            require_module_access(db, user, module)
        if user is not None and management_module:
            require_module_manage(db, user, management_module)
        if feature:
            require_feature(db, empresa_id, feature)
        if limit_key:
            enforce_limit(db, empresa_id, limit_key)
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )
    finally:
        db.close()

    return await call_next(request)
