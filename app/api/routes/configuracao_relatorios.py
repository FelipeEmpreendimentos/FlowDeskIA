from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.database.database import get_db
from app.models.enums import CargoUsuario
from app.models.models import Usuario
from app.services.audit import add_audit_log
from app.services.report_settings import reports_use_finance, set_reports_use_finance


router = APIRouter(prefix="/configuracoes/relatorios", tags=["Configurações de relatórios"])


class ConfiguracaoRelatoriosOut(BaseModel):
    usar_financeiro: bool


class ConfiguracaoRelatoriosUpdate(BaseModel):
    usar_financeiro: bool


@router.get("", response_model=ConfiguracaoRelatoriosOut)
def obter_configuracao_relatorios(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConfiguracaoRelatoriosOut:
    return ConfiguracaoRelatoriosOut(
        usar_financeiro=reports_use_finance(db, current_user.empresa_id)
    )


@router.put("", response_model=ConfiguracaoRelatoriosOut)
def atualizar_configuracao_relatorios(
    data: ConfiguracaoRelatoriosUpdate,
    current_user: Usuario = Depends(require_roles(CargoUsuario.ADMIN)),
    db: Session = Depends(get_db),
) -> ConfiguracaoRelatoriosOut:
    usar_financeiro = set_reports_use_finance(
        db,
        empresa_id=current_user.empresa_id,
        usar_financeiro=data.usar_financeiro,
    )
    add_audit_log(
        db,
        user=current_user,
        action="ATUALIZOU_CONFIG_RELATORIOS",
        entity="configuracoes_relatorios",
        entity_id=current_user.empresa_id,
        details={"usar_financeiro": usar_financeiro},
    )
    db.commit()
    return ConfiguracaoRelatoriosOut(usar_financeiro=usar_financeiro)
