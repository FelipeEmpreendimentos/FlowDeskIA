from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


TomIA = Literal["FORMAL", "EQUILIBRADO", "INFORMAL"]
TamanhoRespostaIA = Literal["CURTA", "MEDIA", "DETALHADA"]
CampoClienteIA = Literal["nome", "email"]
CampoVeiculoIA = Literal["tipo_veiculo", "marca", "modelo", "ano", "cor"]


class ConhecimentoIAItem(BaseModel):
    titulo: str = Field(min_length=1, max_length=120)
    conteudo: str = Field(min_length=1, max_length=1200)


class AICompanySettingsPut(BaseModel):
    saudacao_cliente_novo: str | None = Field(default=None, max_length=800)
    saudacao_cliente_conhecido: str | None = Field(default=None, max_length=800)
    mensagem_transferencia: str | None = Field(default=None, max_length=800)
    mensagem_fora_escopo: str | None = Field(default=None, max_length=800)
    mensagem_indisponibilidade: str | None = Field(default=None, max_length=800)
    mensagem_despedida: str | None = Field(default=None, max_length=800)
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
    tentativas_antes_handoff: int = Field(default=2, ge=1, le=5)
    campos_cliente_obrigatorios: list[CampoClienteIA] = Field(default_factory=lambda: ["nome"])
    campos_veiculo_obrigatorios: list[CampoVeiculoIA] = Field(default_factory=lambda: ["tipo_veiculo"])
    conhecimento: list[ConhecimentoIAItem] = Field(default_factory=list, max_length=40)


class AICompanySettingsOut(ORMModel):
    empresa_id: int
    saudacao_cliente_novo: str | None
    saudacao_cliente_conhecido: str | None
    mensagem_transferencia: str | None
    mensagem_fora_escopo: str | None
    mensagem_indisponibilidade: str | None
    mensagem_despedida: str | None
    tom: TomIA
    tamanho_resposta: TamanhoRespostaIA
    usar_emojis: bool
    criar_cliente_auto: bool
    criar_veiculo_auto: bool
    pode_agendar: bool
    pode_reagendar: bool
    pode_cancelar: bool
    confirmar_acoes: bool
    transferir_fora_escopo: bool
    tentativas_antes_handoff: int
    campos_cliente_obrigatorios: list[CampoClienteIA]
    campos_veiculo_obrigatorios: list[CampoVeiculoIA]
    conhecimento: list[ConhecimentoIAItem]
