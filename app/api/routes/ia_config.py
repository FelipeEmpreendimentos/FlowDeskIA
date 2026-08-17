from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.database import get_db
from app.models.ai import AICompanySettings
from app.models.enums import CargoUsuario
from app.models.models import ConfigIA, Usuario
from app.schemas.ai import AICompanySettingsOut, AICompanySettingsPut
from app.services.audit import add_audit_log
from app.services.db_utils import commit_or_conflict

router = APIRouter(prefix="/configuracoes/ia-operacional", tags=["Configurações - IA operacional"])


def _get_or_create_settings(db: Session, empresa_id: int) -> AICompanySettings:
    item = db.scalar(
        select(AICompanySettings).where(AICompanySettings.empresa_id == empresa_id)
    )
    if item is None:
        item = AICompanySettings(empresa_id=empresa_id)
        db.add(item)
        db.flush()
    return item


def _get_or_create_base_config(db: Session, empresa_id: int) -> ConfigIA:
    item = db.scalar(select(ConfigIA).where(ConfigIA.empresa_id == empresa_id))
    if item is None:
        item = ConfigIA(
            empresa_id=empresa_id,
            nome_assistente="Assistente",
            mensagem_boas_vindas=None,
            prompt=None,
            temperatura=Decimal("0.70"),
        )
        db.add(item)
        db.flush()
    return item


def _out(settings: AICompanySettings, base: ConfigIA) -> AICompanySettingsOut:
    return AICompanySettingsOut(
        empresa_id=settings.empresa_id,
        nome_assistente=base.nome_assistente,
        prompt_adicional=base.prompt,
        saudacao_cliente_novo=settings.saudacao_cliente_novo,
        saudacao_cliente_conhecido=settings.saudacao_cliente_conhecido,
        mensagem_transferencia=settings.mensagem_transferencia,
        mensagem_fora_escopo=settings.mensagem_fora_escopo,
        mensagem_indisponibilidade=settings.mensagem_indisponibilidade,
        mensagem_despedida=settings.mensagem_despedida,
        tom=settings.tom,
        tamanho_resposta=settings.tamanho_resposta,
        usar_emojis=settings.usar_emojis,
        criar_cliente_auto=settings.criar_cliente_auto,
        criar_veiculo_auto=settings.criar_veiculo_auto,
        pode_agendar=settings.pode_agendar,
        pode_reagendar=settings.pode_reagendar,
        pode_cancelar=settings.pode_cancelar,
        confirmar_acoes=settings.confirmar_acoes,
        transferir_fora_escopo=settings.transferir_fora_escopo,
        tentativas_antes_handoff=settings.tentativas_antes_handoff,
        campos_cliente_obrigatorios=settings.campos_cliente_obrigatorios or [],
        campos_veiculo_obrigatorios=settings.campos_veiculo_obrigatorios or [],
        conhecimento=settings.conhecimento or [],
    )


@router.get("", response_model=AICompanySettingsOut)
def obter_configuracao_ia_operacional(
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> AICompanySettingsOut:
    settings = _get_or_create_settings(db, current_user.empresa_id)
    base = _get_or_create_base_config(db, current_user.empresa_id)
    db.commit()
    return _out(settings, base)


@router.put("", response_model=AICompanySettingsOut)
def salvar_configuracao_ia_operacional(
    data: AICompanySettingsPut,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> AICompanySettingsOut:
    settings = _get_or_create_settings(db, current_user.empresa_id)
    base = _get_or_create_base_config(db, current_user.empresa_id)

    base.nome_assistente = data.nome_assistente.strip()
    base.prompt = data.prompt_adicional.strip() if data.prompt_adicional else None
    if data.saudacao_cliente_novo:
        base.mensagem_boas_vindas = data.saudacao_cliente_novo.strip()

    values = data.model_dump(exclude={"nome_assistente", "prompt_adicional"})
    values["conhecimento"] = [entry.model_dump() for entry in data.conhecimento]
    for key, value in values.items():
        setattr(settings, key, value)

    add_audit_log(
        db,
        user=current_user,
        action="ATUALIZOU_CONFIG_IA_OPERACIONAL",
        entity="ai_company_settings",
        entity_id=current_user.empresa_id,
        details={
            "tom": settings.tom,
            "pode_agendar": settings.pode_agendar,
            "pode_reagendar": settings.pode_reagendar,
            "pode_cancelar": settings.pode_cancelar,
            "criar_cliente_auto": settings.criar_cliente_auto,
            "criar_veiculo_auto": settings.criar_veiculo_auto,
        },
    )
    commit_or_conflict(db, settings)
    return _out(settings, base)
