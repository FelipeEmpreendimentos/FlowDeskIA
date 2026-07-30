from collections.abc import Awaitable, Callable

from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.security import decode_access_token
from app.database.database import SessionLocal
from app.services.plans import enforce_limit, require_feature

FEATURE_PATHS = {
    "/api/v1/agendamentos": "AGENDA",
    "/api/v1/clientes": "CLIENTES",
    "/api/v1/veiculos": "VEICULOS",
    "/api/v1/servicos": "SERVICOS",
    "/api/v1/conversas": "CONVERSAS",
    "/api/v1/notificacoes": "NOTIFICACOES",
}

CREATE_LIMITS = {
    "/api/v1/agendamentos": "agendamentos_mes",
    "/api/v1/conversas": "conversas_mes",
    "/api/v1/configuracoes/integracoes": "canais",
}


def _company_id_from_request(request: Request) -> int | None:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    try:
        payload = decode_access_token(token)
        if payload.get("kind", "company_user") != "company_user":
            return None
        return int(payload["empresa_id"])
    except (ValueError, KeyError, TypeError):
        return None


def _feature_for_path(path: str) -> str | None:
    for prefix, feature in FEATURE_PATHS.items():
        if path == prefix or path.startswith(f"{prefix}/"):
            return feature
    return None


async def plan_access_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    empresa_id = _company_id_from_request(request)
    if empresa_id is None:
        return await call_next(request)

    path = request.url.path.rstrip("/") or "/"
    feature = _feature_for_path(path)
    limit_key = CREATE_LIMITS.get(path) if request.method == "POST" else None

    if feature is None and limit_key is None:
        return await call_next(request)

    db = SessionLocal()
    try:
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
