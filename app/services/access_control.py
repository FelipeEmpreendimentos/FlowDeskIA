from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
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

EMPLOYEE_DEFAULTS = {
    "AGENDA",
    "CHAT_INTERNO",
    "CONVERSAS",
    "CLIENTES",
    "VEICULOS",
    "SERVICOS",
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


def company_module_enabled(db: Session, empresa_id: int, module: str) -> bool:
    module = validate_module(module)
    try:
        row = db.scalar(
            select(EmpresaModulo).where(
                EmpresaModulo.empresa_id == empresa_id,
                EmpresaModulo.modulo == module,
            )
        )
    except ProgrammingError:
        db.rollback()
        return True
    return True if row is None else row.ativo


def user_module_access(db: Session, user: Usuario, module: str) -> bool:
    module = validate_module(module)
    if not company_module_enabled(db, user.empresa_id, module):
        return False

    try:
        override = db.scalar(
            select(UsuarioPermissaoModulo).where(
                UsuarioPermissaoModulo.empresa_id == user.empresa_id,
                UsuarioPermissaoModulo.usuario_id == user.id,
                UsuarioPermissaoModulo.modulo == module,
            )
        )
    except ProgrammingError:
        db.rollback()
        override = None

    if override is not None:
        return override.permitido
    return default_access(user.cargo, module)


def effective_permissions(db: Session, user: Usuario) -> dict[str, bool]:
    return {item.code: user_module_access(db, user, item.code) for item in MODULES}


def require_module_access(db: Session, user: Usuario, module: str) -> None:
    if not user_module_access(db, user, module):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Este módulo está desativado ou não foi liberado para o seu usuário.",
        )
