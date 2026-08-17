from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.database import get_db
from app.models.ai import AICompanySettings
from app.models.enums import CargoUsuario
from app.models.models import Usuario
from app.schemas.ai import AICompanySettingsOut, AICompanySettingsPut
from app.services.audit import add_audit_log
from app.services.db_utils import commit_or_conflict

router = APIRouter(prefix="/configuracoes/ia-operacional", tags=["Configurações - IA operacional"])


def _get_or_create(db: Session, empresa_id: int) -> AICompanySettings:
    item = db.scalar(
        select(AICompanySettings).where(AICompanySettings.empresa_id == empresa_id)
    )
    if item is None:
        item = AICompanySettings(empresa_id=empresa_id)
        db.add(item)
        db.flush()
    return item


@router.get("", response_model=AICompanySettingsOut)
def obter_configuracao_ia_operacional(
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> AICompanySettings:
    item = _get_or_create(db, current_user.empresa_id)
    if item.id if hasattr(item, "id") else False:
        pass
    db.commit()
    return item


@router.put("", response_model=AICompanySettingsOut)
def salvar_configuracao_ia_operacional(
    data: AICompanySettingsPut,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> AICompanySettings:
    item = _get_or_create(db, current_user.empresa_id)
    values = data.model_dump()
    values["conhecimento"] = [entry.model_dump() for entry in data.conhecimento]
    for key, value in values.items():
        setattr(item, key, value)

    add_audit_log(
        db,
        user=current_user,
        action="ATUALIZOU_CONFIG_IA_OPERACIONAL",
        entity="ai_company_settings",
        entity_id=current_user.empresa_id,
        details={
            "tom": item.tom,
            "pode_agendar": item.pode_agendar,
            "pode_reagendar": item.pode_reagendar,
            "pode_cancelar": item.pode_cancelar,
            "criar_cliente_auto": item.criar_cliente_auto,
            "criar_veiculo_auto": item.criar_veiculo_auto,
        },
    )
    return commit_or_conflict(db, item)
