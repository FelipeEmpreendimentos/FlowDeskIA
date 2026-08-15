from collections.abc import Awaitable, Callable

from fastapi import HTTPException
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.security import decode_access_token
from app.database.database import SessionLocal
from app.models.models import Usuario
from app.services.access_control import (
    require_module_access,
    require_module_manage,
    user_module_access,
)
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

# A Agenda precisa ler estes cadastros para montar os nomes e opções do
# formulário, mesmo quando as telas desses módulos estiverem bloqueadas.
AGENDA_SUPPORT_READ_PATHS = {
    "/api/v1/clientes",
    "/api/v1/veiculos",
    "/api/v1/servicos",
    "/api/v1/usuarios",
}

CREATE_LIMITS = {
    "/api/v1/agendamentos": "agendamentos_mes",
    "/api/v1/conversas": "conversas_mes",
    "/api/v1/configuracoes/integracoes": "canais",
}

READ_METHODS = {"GET", "HEAD", "OPTIONS"}

MANAGEMENT_EXACT_PATHS = {
    ("POST", "/api/v1/conversas"): "CONVERSAS",
}

MANAGEMENT_MUTATION_PATHS = {
    "/api/v1/agendamentos": "AGENDA",
    "/api/v1/chat-interno/grupos": "CHAT_INTERNO",
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


def _is_numeric_child(path: str, prefix: str) -> bool:
    if not path.startswith(f"{prefix}/"):
        return False
    suffix = path[len(prefix) + 1 :]
    return suffix.isdigit()


def _view_level_mutation_allowed(method: str, path: str) -> bool:
    """Mutações que pertencem ao escopo operacional de Visualizar.

    A autorização fina continua nas rotas. O middleware apenas deixa a
    requisição chegar ao backend para que ele valide propriedade/campos.
    """
    if path == "/api/v1/agendamentos" and method == "POST":
        return True
    if _is_numeric_child(path, "/api/v1/agendamentos") and method in {
        "PATCH",
        "DELETE",
    }:
        return True
    if _is_numeric_child(path, "/api/v1/clientes") and method == "PATCH":
        return True
    if _is_numeric_child(path, "/api/v1/veiculos") and method == "PATCH":
        return True
    return False


def _management_module(method: str, path: str) -> str | None:
    exact = MANAGEMENT_EXACT_PATHS.get((method, path))
    if exact:
        return exact
    if method in READ_METHODS or _view_level_mutation_allowed(method, path):
        return None
    return _value_for_path(path, MANAGEMENT_MUTATION_PATHS)


def _agenda_support_read_allowed(
    db,
    user: Usuario,
    method: str,
    path: str,
) -> bool:
    if method not in READ_METHODS:
        return False
    if not any(
        path == prefix or path.startswith(f"{prefix}/")
        for prefix in AGENDA_SUPPORT_READ_PATHS
    ):
        return False
    return user_module_access(db, user, "AGENDA")


def _validate_access_sync(
    *,
    user_id: int,
    empresa_id: int,
    method: str,
    path: str,
    feature: str | None,
    module: str | None,
    management_module: str | None,
    limit_key: str | None,
) -> None:
    """Executa as consultas síncronas de autorização fora do event loop.

    O backend usa SQLAlchemy/psycopg2 síncronos. Fazer essas consultas dentro
    do middleware async bloqueava o único event loop do Uvicorn durante cada
    round trip até o banco remoto, serializando requisições concorrentes do
    dashboard. O middleware chama esta função via run_in_threadpool.
    """
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
            try:
                require_module_access(db, user, module)
            except HTTPException:
                if not _agenda_support_read_allowed(
                    db,
                    user,
                    method,
                    path,
                ):
                    raise
        if user is not None and management_module:
            require_module_manage(db, user, management_module)
        if feature:
            require_feature(db, empresa_id, feature)
        if limit_key:
            enforce_limit(db, empresa_id, limit_key)
    finally:
        db.close()


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

    try:
        await run_in_threadpool(
            _validate_access_sync,
            user_id=user_id,
            empresa_id=empresa_id,
            method=request.method,
            path=path,
            feature=feature,
            module=module,
            management_module=management_module,
            limit_key=limit_key,
        )
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )

    return await call_next(request)
