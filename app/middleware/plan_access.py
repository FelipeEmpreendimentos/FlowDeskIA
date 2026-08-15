from collections.abc import Awaitable, Callable

from fastapi import HTTPException
from sqlalchemy import literal, select
from sqlalchemy.exc import ProgrammingError
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.security import decode_access_token
from app.database.database import SessionLocal
from app.models.access_control import EmpresaModulo, UsuarioPermissaoModulo
from app.models.models import Empresa, Usuario
from app.models.platform import EmpresaPlataforma, PlanoConfiguracao
from app.services.access_control import (
    VIEW_ONLY_MODULES,
    default_access,
    default_manage,
    require_module_access,
    require_module_manage,
    user_module_access,
)
from app.services.plans import RECURSOS_PADRAO, enforce_limit, require_feature

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
    """Mutações que pertencem ao escopo operacional de Visualizar."""
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


def _agenda_support_read_path(method: str, path: str) -> bool:
    return method in READ_METHODS and any(
        path == prefix or path.startswith(f"{prefix}/")
        for prefix in AGENDA_SUPPORT_READ_PATHS
    )


def _agenda_support_read_allowed(
    db,
    user: Usuario,
    method: str,
    path: str,
) -> bool:
    if not _agenda_support_read_path(method, path):
        return False
    return user_module_access(db, user, "AGENDA")


def _module_expressions(
    *,
    module: str | None,
    user_id: int,
    empresa_id: int,
    prefix: str,
):
    if module is None:
        return (
            literal(None).label(f"{prefix}_enabled"),
            literal(None).label(f"{prefix}_view"),
            literal(None).label(f"{prefix}_manage"),
        )

    enabled = (
        select(EmpresaModulo.ativo)
        .where(
            EmpresaModulo.empresa_id == empresa_id,
            EmpresaModulo.modulo == module,
        )
        .limit(1)
        .scalar_subquery()
        .label(f"{prefix}_enabled")
    )
    view = (
        select(UsuarioPermissaoModulo.permitido)
        .where(
            UsuarioPermissaoModulo.empresa_id == empresa_id,
            UsuarioPermissaoModulo.usuario_id == user_id,
            UsuarioPermissaoModulo.modulo == module,
        )
        .limit(1)
        .scalar_subquery()
        .label(f"{prefix}_view")
    )
    manage = (
        select(UsuarioPermissaoModulo.pode_gerenciar)
        .where(
            UsuarioPermissaoModulo.empresa_id == empresa_id,
            UsuarioPermissaoModulo.usuario_id == user_id,
            UsuarioPermissaoModulo.modulo == module,
        )
        .limit(1)
        .scalar_subquery()
        .label(f"{prefix}_manage")
    )
    return enabled, view, manage


def _module_access_from_values(
    user: Usuario,
    module: str,
    enabled_value,
    view_override,
) -> bool:
    enabled = True if enabled_value is None else bool(enabled_value)
    if not enabled:
        return False
    if view_override is not None:
        return bool(view_override)
    return default_access(user.cargo, module)


def _module_manage_from_values(
    user: Usuario,
    module: str,
    enabled_value,
    view_override,
    manage_override,
) -> bool:
    if module in VIEW_ONLY_MODULES:
        return False
    if not _module_access_from_values(user, module, enabled_value, view_override):
        return False
    if manage_override is not None:
        return bool(manage_override)
    return default_manage(user.cargo, module)


def _feature_allowed(
    configuracao: PlanoConfiguracao | None,
    plataforma: EmpresaPlataforma | None,
    feature: str,
) -> bool:
    recursos = dict(RECURSOS_PADRAO)
    if configuracao and configuracao.recursos:
        recursos.update(
            {key: bool(value) for key, value in configuracao.recursos.items()}
        )
    if plataforma and plataforma.recursos_personalizados:
        recursos.update(
            {
                key: bool(value)
                for key, value in plataforma.recursos_personalizados.items()
            }
        )

    ia_ativa = bool(
        configuracao
        and (
            configuracao.ia_incluida
            or (
                configuracao.ia_adicional_disponivel
                and plataforma
                and plataforma.ia_adicional_ativo
            )
        )
    )
    recursos["INTELIGENCIA_ARTIFICIAL"] = ia_ativa
    return bool(recursos.get(feature, False))


def _validate_access_fallback(
    db,
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
            if not _agenda_support_read_allowed(db, user, method, path):
                raise
    if user is not None and management_module:
        require_module_manage(db, user, management_module)
    if feature:
        require_feature(db, empresa_id, feature)
    if limit_key:
        enforce_limit(db, empresa_id, limit_key)


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
) -> dict[str, object] | None:
    """Valida acesso e carrega contexto com um único round trip principal."""
    db = SessionLocal()
    try:
        module_exprs = _module_expressions(
            module=module,
            user_id=user_id,
            empresa_id=empresa_id,
            prefix="module",
        )
        management_exprs = _module_expressions(
            module=management_module,
            user_id=user_id,
            empresa_id=empresa_id,
            prefix="management",
        )
        agenda_exprs = _module_expressions(
            module="AGENDA" if _agenda_support_read_path(method, path) else None,
            user_id=user_id,
            empresa_id=empresa_id,
            prefix="agenda",
        )

        try:
            row = db.execute(
                select(
                    Usuario,
                    Empresa,
                    EmpresaPlataforma,
                    PlanoConfiguracao,
                    *module_exprs,
                    *management_exprs,
                    *agenda_exprs,
                )
                .join(Empresa, Empresa.id == Usuario.empresa_id)
                .outerjoin(
                    EmpresaPlataforma,
                    EmpresaPlataforma.empresa_id == Empresa.id,
                )
                .outerjoin(
                    PlanoConfiguracao,
                    PlanoConfiguracao.plano_id == Empresa.plano_id,
                )
                .where(
                    Usuario.id == user_id,
                    Usuario.empresa_id == empresa_id,
                    Usuario.ativo.is_(True),
                )
            ).one_or_none()
        except ProgrammingError:
            db.rollback()
            _validate_access_fallback(
                db,
                user_id=user_id,
                empresa_id=empresa_id,
                method=method,
                path=path,
                feature=feature,
                module=module,
                management_module=management_module,
                limit_key=limit_key,
            )
            return None

        if row is None:
            return None

        (
            user,
            empresa,
            plataforma,
            configuracao,
            module_enabled,
            module_view,
            _module_manage,
            management_enabled,
            management_view,
            management_manage,
            agenda_enabled,
            agenda_view,
            _agenda_manage,
        ) = row

        if module and not _module_access_from_values(
            user,
            module,
            module_enabled,
            module_view,
        ):
            agenda_allowed = bool(
                _agenda_support_read_path(method, path)
                and _module_access_from_values(
                    user,
                    "AGENDA",
                    agenda_enabled,
                    agenda_view,
                )
            )
            if not agenda_allowed:
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "Este módulo está desativado ou não foi liberado para o seu usuário."
                    ),
                )

        if management_module and not _module_manage_from_values(
            user,
            management_module,
            management_enabled,
            management_view,
            management_manage,
        ):
            raise HTTPException(
                status_code=403,
                detail=(
                    "Você pode visualizar este módulo, mas não possui permissão para gerenciá-lo."
                ),
            )

        if feature and not _feature_allowed(configuracao, plataforma, feature):
            raise HTTPException(
                status_code=403,
                detail=(
                    f"O recurso {feature.replace('_', ' ').title()} não está liberado no plano atual."
                ),
            )

        # Limites são relevantes apenas em criação. A validação estática acima
        # já foi agregada; o contador de uso permanece separado para preservar
        # a consistência no momento da escrita.
        if limit_key:
            enforce_limit(db, empresa_id, limit_key)

        return {
            "user_id": user.id,
            "empresa_id": user.empresa_id,
            "user": user,
            "empresa_ativo": empresa.ativo,
            "empresa_timezone": empresa.timezone,
            "plataforma_status": plataforma.status if plataforma else None,
        }
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
        snapshot = await run_in_threadpool(
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
        if snapshot is not None:
            request.state.flowdesk_auth_context = snapshot
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )

    return await call_next(request)
