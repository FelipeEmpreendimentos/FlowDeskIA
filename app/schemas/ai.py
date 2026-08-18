from typing import Literal

from pydantic import BaseModel, Field


TomIA = Literal["FORMAL", "EQUILIBRADO", "INFORMAL"]
TamanhoRespostaIA = Literal["CURTA", "MEDIA", "DETALHADA"]
CampoClienteIA = Literal["nome", "email"]
CampoVeiculoIA = Literal["tipo_veiculo", "marca", "modelo", "ano", "cor"]
AcaoMenuIA = Literal[
    "AGENDAR",
    "CONSULTAR_AGENDAMENTO",
    "REAGENDAR",
    "CANCELAR",
    "SERVICOS_PRECOS",
    "HUMANO",
]


class ConhecimentoIAItem(BaseModel):
    titulo: str = Field(min_length=1, max_length=120)
    conteudo: str = Field(min_length=1, max_length=1200)


class MenuIAItem(BaseModel):
    acao: AcaoMenuIA
    rotulo: str = Field(min_length=1, max_length=40)
    ativo: bool = True
    ordem: int = Field(default=10, ge=0, le=999)


class AICompanySettingsPut(BaseModel):
    nome_assistente: str = Field(default="Assistente", min_length=1, max_length=80)
    prompt_adicional: str | None = Field(default=None, max_length=4000)
    saudacao_cliente_novo: str | None = Field(default=None, max_length=800)
    saudacao_cliente_conhecido: str | None = Field(default=None, max_length=800)
    mensagem_transferencia: str | None = Field(default=None, max_length=800)
    mensagem_fora_escopo: str | None = Field(default=None, max_length=800)
    mensagem_indisponibilidade: str | None = Field(default=None, max_length=800)
    mensagem_despedida: str | None = Field(default=None, max_length=800)
    texto_menu_principal: str | None = Field(default=None, max_length=500)
    tom: TomIA = "EQUILIBRADO"
    tamanho_resposta: TamanhoRespostaIA = "CURTA"
    usar_emojis: bool = True
    criar_cliente_auto: bool = True
    criar_veiculo_auto: bool = True
    pode_agendar: bool = True
    pode_reagendar: bool = True
    pode_cancelar: bool = True
    confirmar_acoes: bool = True
    transferir_fora_escopo: bool = True
    fluxo_guiado_ativo: bool = True
    mostrar_interpretacao: bool = True
    tentativas_antes_handoff: int = Field(default=2, ge=1, le=5)
    campos_cliente_obrigatorios: list[CampoClienteIA] = Field(default_factory=lambda: ["nome"])
    campos_veiculo_obrigatorios: list[CampoVeiculoIA] = Field(default_factory=lambda: ["tipo_veiculo"])
    conhecimento: list[ConhecimentoIAItem] = Field(default_factory=list, max_length=40)
    menu_principal: list[MenuIAItem] = Field(default_factory=list, max_length=6)


class AICompanySettingsOut(AICompanySettingsPut):
    empresa_id: int
