from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.database import get_db
from app.models.ai import AICompanySettings, DEFAULT_AI_MENU
from app.models.enums import CargoUsuario
from app.models.models import ConfigIA, Usuario
from app.schemas.ai import AICompanySettingsOut, AICompanySettingsPut
from app.services.audit import add_audit_log
from app.services.db_utils import commit_or_conflict

router = APIRouter(prefix="/configuracoes/ia-operacional", tags=["Configurações - IA operacional"])

POLICY_MARKER = "\n\n[FLOWDESK_POLITICA_OPERACIONAL]\n"


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


def _user_prompt(value: str | None) -> str | None:
    if not value:
        return None
    return value.split(POLICY_MARKER, 1)[0].strip() or None


def _policy_prompt(data: AICompanySettingsPut) -> str:
    def yesno(value: bool) -> str:
        return "SIM" if value else "NÃO"

    lines = [
        "POLÍTICA OPERACIONAL CONFIGURADA PELA EMPRESA:",
        f"- Fluxo guiado com opções rápidas: {yesno(data.fluxo_guiado_ativo)}.",
        f"- Mostrar ao cliente o que foi interpretado em mensagens livres: {yesno(data.mostrar_interpretacao)}.",
        f"- Criar cliente automaticamente: {yesno(data.criar_cliente_auto)}.",
        f"- Criar veículo automaticamente: {yesno(data.criar_veiculo_auto)}.",
        f"- Pode agendar: {yesno(data.pode_agendar)}.",
        f"- Pode reagendar: {yesno(data.pode_reagendar)}.",
        f"- Pode cancelar: {yesno(data.pode_cancelar)}.",
        f"- Exigir confirmação antes de ações: {yesno(data.confirmar_acoes)}.",
        f"- Transferir pedidos fora do escopo: {yesno(data.transferir_fora_escopo)}.",
        f"- Máximo de tentativas sem entender antes de transferir: {data.tentativas_antes_handoff}.",
        "- Campos de cliente necessários para concluir operações: "
        + (", ".join(data.campos_cliente_obrigatorios) or "nenhum adicional"),
        "- Campos de veículo necessários para concluir operações: "
        + (", ".join(data.campos_veiculo_obrigatorios) or "nenhum adicional"),
    ]

    if data.mensagem_fora_escopo:
        lines.append(
            "- Ao explicar que um pedido está fora do escopo, use como referência natural esta mensagem: "
            + data.mensagem_fora_escopo.strip()
        )
    if data.mensagem_indisponibilidade:
        lines.append(
            "- Quando não houver horários, use como referência natural esta mensagem: "
            + data.mensagem_indisponibilidade.strip()
        )
    if data.mensagem_despedida:
        lines.append(
            "- Quando o atendimento estiver realmente concluído, use como referência natural esta despedida: "
            + data.mensagem_despedida.strip()
        )
    if data.mensagem_transferencia:
        lines.append(
            "- Ao transferir para humano, use como referência esta mensagem: "
            + data.mensagem_transferencia.strip()
        )

    if not data.transferir_fora_escopo:
        lines.append(
            "- Para pedido fora do escopo, apenas informe que a empresa não oferece o serviço; NÃO transfira somente por esse motivo."
        )
    else:
        lines.append(
            "- Para pedido claramente fora do escopo, informe que a empresa não oferece o serviço e depois use transferir_para_humano."
        )

    return "\n".join(lines)


def _combined_prompt(data: AICompanySettingsPut) -> str:
    user = data.prompt_adicional.strip() if data.prompt_adicional else ""
    policy = _policy_prompt(data)
    return (user + POLICY_MARKER + policy).strip()


def _out(settings: AICompanySettings, base: ConfigIA) -> AICompanySettingsOut:
    return AICompanySettingsOut(
        empresa_id=settings.empresa_id,
        nome_assistente=base.nome_assistente,
        prompt_adicional=_user_prompt(base.prompt),
        saudacao_cliente_novo=settings.saudacao_cliente_novo,
        saudacao_cliente_conhecido=settings.saudacao_cliente_conhecido,
        mensagem_transferencia=settings.mensagem_transferencia,
        mensagem_fora_escopo=settings.mensagem_fora_escopo,
        mensagem_indisponibilidade=settings.mensagem_indisponibilidade,
        mensagem_despedida=settings.mensagem_despedida,
        texto_menu_principal=settings.texto_menu_principal,
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
        fluxo_guiado_ativo=settings.fluxo_guiado_ativo,
        mostrar_interpretacao=settings.mostrar_interpretacao,
        tentativas_antes_handoff=settings.tentativas_antes_handoff,
        campos_cliente_obrigatorios=settings.campos_cliente_obrigatorios or [],
        campos_veiculo_obrigatorios=settings.campos_veiculo_obrigatorios or [],
        conhecimento=settings.conhecimento or [],
        menu_principal=settings.menu_principal or [dict(item) for item in DEFAULT_AI_MENU],
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
    if not settings.menu_principal:
        settings.menu_principal = [dict(item) for item in DEFAULT_AI_MENU]
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
    base.prompt = _combined_prompt(data)
    if data.saudacao_cliente_novo:
        base.mensagem_boas_vindas = data.saudacao_cliente_novo.strip()

    values = data.model_dump(
        exclude={"nome_assistente", "prompt_adicional", "conhecimento", "menu_principal"}
    )
    values["conhecimento"] = [entry.model_dump() for entry in data.conhecimento]
    values["menu_principal"] = [entry.model_dump() for entry in data.menu_principal]
    if not values["menu_principal"]:
        values["menu_principal"] = [dict(item) for item in DEFAULT_AI_MENU]
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
            "fluxo_guiado_ativo": settings.fluxo_guiado_ativo,
            "mostrar_interpretacao": settings.mostrar_interpretacao,
            "menu_ativo": [
                item.get("acao")
                for item in (settings.menu_principal or [])
                if isinstance(item, dict) and item.get("ativo")
            ],
            "pode_agendar": settings.pode_agendar,
            "pode_reagendar": settings.pode_reagendar,
            "pode_cancelar": settings.pode_cancelar,
            "criar_cliente_auto": settings.criar_cliente_auto,
            "criar_veiculo_auto": settings.criar_veiculo_auto,
            "transferir_fora_escopo": settings.transferir_fora_escopo,
        },
    )
    commit_or_conflict(db, settings)
    return _out(settings, base)
