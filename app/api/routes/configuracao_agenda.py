from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.database.database import get_db
from app.models.agenda_settings import ConfiguracaoAgenda
from app.models.enums import CargoUsuario
from app.models.models import Usuario
from app.schemas.agenda_settings import (
    ConfiguracaoAgendaOut,
    ConfiguracaoAgendaUpdate,
)
from app.services.audit import add_audit_log
from app.services.db_utils import commit_or_conflict

router = APIRouter(prefix="/configuracoes-agenda", tags=["Configurações da agenda"])


def _obter_ou_criar(db: Session, empresa_id: int) -> ConfiguracaoAgenda:
    configuracao = db.get(ConfiguracaoAgenda, empresa_id)
    if configuracao is not None:
        return configuracao

    configuracao = ConfiguracaoAgenda(
        empresa_id=empresa_id,
        intervalo_minutos=30,
    )
    db.add(configuracao)
    return commit_or_conflict(db, configuracao)


@router.get("", response_model=ConfiguracaoAgendaOut)
def obter_configuracao_agenda(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConfiguracaoAgenda:
    return _obter_ou_criar(db, current_user.empresa_id)


@router.patch("", response_model=ConfiguracaoAgendaOut)
def atualizar_configuracao_agenda(
    data: ConfiguracaoAgendaUpdate,
    current_user: Usuario = Depends(require_roles(CargoUsuario.ADMIN)),
    db: Session = Depends(get_db),
) -> ConfiguracaoAgenda:
    configuracao = _obter_ou_criar(db, current_user.empresa_id)
    configuracao.intervalo_minutos = data.intervalo_minutos

    add_audit_log(
        db,
        user=current_user,
        action="ATUALIZOU_CONFIGURACAO_AGENDA",
        entity="configuracoes_agenda",
        entity_id=current_user.empresa_id,
        details={"intervalo_minutos": data.intervalo_minutos},
    )
    return commit_or_conflict(db, configuracao)
