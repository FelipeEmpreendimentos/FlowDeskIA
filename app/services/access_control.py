from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.models.access_control import EmpresaModulo, UsuarioPermissaoModulo
from app.models.enums import CargoUsuario
from app.models.models import Usuario


@dataclass(frozen=True)
class ModuleDefinition:
    code: str
    name: str
    description: str


MODULES = (
    ModuleDefinition("AGENDA", "Agenda", "Agendamentos, disponibilidade e histórico."),
    ModuleDefinition("CHAT_INTERNO", "Chat interno", "Conversas internas entre a equipe."),
    ModuleDefinition("CONVERSAS", "Conversas", "Atendimento e relacionamento com clientes."),
    ModuleDefinition("CLIENTES", "Clientes", "Cadastro e gestão da base de clientes."),
    ModuleDefinition("VEICULOS", "Veículos", "Veículos vinculados aos clientes."),
    ModuleDefinition("SERVICOS", "Serviços", "Catálogo, preços e duração dos serviços."),
    ModuleDefinition("FINANCEIRO", "Financeiro", "Recebimentos, pendências e estornos."),
    ModuleDefinition("RELATORIOS", "Relatórios", "Indicadores de operação e desempenho."),
    ModuleDefinition("EQUIPE", "Equipe", "Usuários, jornadas e bloqueios da agenda."),
)
MODULE_CODES = {item.code for item in MODULES}
VIEW_ONLY_MODULES = {"RELATORIOS"}

EMPLOYEE_DEFAULTS = {
    "AGENDA",
    "CHAT_INTERNO",
    "CONVERSAS",
    "CLIENTES",
    "VEICULOS",
    "SERVICOS",
    "FINANCEIRO",
}


def validate_module(module: str) -> str:
    normalized = module.strip().upper()
    if normalized not in MODULE_CODES:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Módulo não encontrado.",
        )
    return normalized


def default_access(cargo: CargoUsuario, module: str) -> bool:
    if cargo in {CargoUsuario.ADMIN, CargoUsuario.GERENTE}:
        return True
    return module in EMPLOYEE_DEFAULTS


def default_manage(cargo: CargoUsuario, module: str) -> bool:
    if module in VIEW_ONLY_MODULES:
        return False
    return cargo in {CargoUsuario.ADMIN, CargoUsuario.GERENTE}


def _module_state(
    db: Session,
    user: Usuario,
    module: str,
) -> tuple[bool, bool | None, bool | None]:
    """Carrega estado da empresa e overrides do usuário em um único round trip."""
    module = validate_module(module)
    company_enabled = (
        select(EmpresaModulo.ativo)
        .where(
            EmpresaModulo.empresa_id == user.empresa_id,
            EmpresaModulo.modulo == module,
        )
        .limit(1)
        .scalar_subquery()
    )
    view_override = (
        select(UsuarioPermissaoModulo.permitido)
        .where(
            UsuarioPermissaoModulo.empresa_id == user.empresa_id,
            UsuarioPermissaoModulo.usuario_id == user.id,
            UsuarioPermissaoModulo.modulo == module,
        )
        .limit(1)
        .scalar_subquery()
    )
    manage_override = (
        select(UsuarioPermissaoModulo.pode_gerenciar)
        .where(
            UsuarioPermissaoModulo.empresa_id == user.empresa_id,
            UsuarioPermissaoModulo.usuario_id == user.id,
            UsuarioPermissaoModulo.modulo == module,
        )
        .limit(1)
        .scalar_subquery()
    )

    try:
        row = db.execute(
            select(company_enabled, view_override, manage_override)
        ).one()
    except ProgrammingError:
        db.rollback()
        return True, None, None

    enabled_value, view_value, manage_value = row
    return (
        True if enabled_value is None else bool(enabled_value),
        view_value,
        manage_value,
    )


def _permission_sets_from_rows(
    user: Usuario,
    company_rows: dict[str, bool],
    user_rows: dict[str, tuple[bool | None, bool | None]],
) -> tuple[dict[str, bool], dict[str, bool]]:
    permissions: dict[str, bool] = {}
    management: dict[str, bool] = {}

    for item in MODULES:
        module = item.code
        enabled = company_rows.get(module, True)
        view_override, manage_override = user_rows.get(module, (None, None))
        view_allowed = bool(
            enabled
            and (
                view_override
                if view_override is not None
                else default_access(user.cargo, module)
            )
        )
        permissions[module] = view_allowed

        if module in VIEW_ONLY_MODULES or not view_allowed:
            management[module] = False
        else:
            management[module] = bool(
                manage_override
                if manage_override is not None
                else default_manage(user.cargo, module)
            )

    return permissions, management


def effective_permission_sets(
    db: Session,
    user: Usuario,
) -> tuple[dict[str, bool], dict[str, bool]]:
    """Calcula todas as permissões em uma única consulta ao banco."""
    try:
        rows = db.execute(
            select(
                EmpresaModulo.modulo,
                EmpresaModulo.ativo,
                UsuarioPermissaoModulo.permitido,
                UsuarioPermissaoModulo.pode_gerenciar,
            )
            .outerjoin(
                UsuarioPermissaoModulo,
                and_(
                    UsuarioPermissaoModulo.empresa_id == EmpresaModulo.empresa_id,
                    UsuarioPermissaoModulo.usuario_id == user.id,
                    UsuarioPermissaoModulo.modulo == EmpresaModulo.modulo,
                ),
            )
            .where(
                EmpresaModulo.empresa_id == user.empresa_id,
                EmpresaModulo.modulo.in_(MODULE_CODES),
            )
        ).all()
        company_rows = {
            module: bool(enabled)
            for module, enabled, _view, _manage in rows
        }
        user_rows = {
            module: (view_override, manage_override)
            for module, _enabled, view_override, manage_override in rows
            if view_override is not None or manage_override is not None
        }
    except ProgrammingError:
        db.rollback()
        company_rows = {}
        user_rows = {}

    return _permission_sets_from_rows(user, company_rows, user_rows)


def company_module_enabled(db: Session, empresa_id: int, module: str) -> bool:
    module = validate_module(module)
    try:
        row = db.scalar(
            select(EmpresaModulo.ativo).where(
                EmpresaModulo.empresa_id == empresa_id,
                EmpresaModulo.modulo == module,
            )
        )
    except ProgrammingError:
        db.rollback()
        return True
    return True if row is None else bool(row)


def user_module_access(db: Session, user: Usuario, module: str) -> bool:
    module = validate_module(module)
    enabled, view_override, _manage_override = _module_state(db, user, module)
    if not enabled:
        return False
    if view_override is not None:
        return bool(view_override)
    return default_access(user.cargo, module)


def user_module_manage(db: Session, user: Usuario, module: str) -> bool:
    module = validate_module(module)
    if module in VIEW_ONLY_MODULES:
        return False

    enabled, view_override, manage_override = _module_state(db, user, module)
    if not enabled:
        return False

    view_allowed = (
        bool(view_override)
        if view_override is not None
        else default_access(user.cargo, module)
    )
    if not view_allowed:
        return False

    if manage_override is not None:
        return bool(manage_override)
    return default_manage(user.cargo, module)


def effective_permissions(db: Session, user: Usuario) -> dict[str, bool]:
    return effective_permission_sets(db, user)[0]


def effective_management_permissions(db: Session, user: Usuario) -> dict[str, bool]:
    return effective_permission_sets(db, user)[1]


def require_module_access(db: Session, user: Usuario, module: str) -> None:
    if not user_module_access(db, user, module):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Este módulo está desativado ou não foi liberado para o seu usuário.",
        )


def require_module_manage(db: Session, user: Usuario, module: str) -> None:
    if not user_module_manage(db, user, module):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Você pode visualizar este módulo, mas não possui permissão para gerenciá-lo.",
        )
