from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.enums import (
    CargoUsuario,
    FormaPagamento,
    OrigemAgendamento,
    OrigemConversa,
    RemetenteMensagem,
    StatusAgendamento,
    StatusAssinatura,
    StatusCliente,
    StatusConversa,
    TipoIntegracao,
    TipoMensagem,
)
from app.schemas.common import ORMModel


TipoVeiculo = Literal["HATCH", "SEDAN", "SUV", "CAMINHONETE", "OUTRO"]


class EmpresaOut(ORMModel):
    id: int
    nome: str
    cnpj: str
    telefone: str | None
    email: str | None
    plano_id: int | None
    logo: str | None
    cidade: str | None
    estado: str | None
    timezone: str
    ativo: bool
    horario_abertura: time | None
    horario_fechamento: time | None
    created_at: datetime
    updated_at: datetime


class EmpresaUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=150)
    telefone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=150)
    logo: str | None = Field(default=None, max_length=255)
    cidade: str | None = Field(default=None, max_length=100)
    estado: str | None = Field(default=None, min_length=2, max_length=2)
    timezone: str | None = Field(default=None, max_length=50)
    horario_abertura: time | None = None
    horario_fechamento: time | None = None


class UsuarioCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    email: str = Field(min_length=3, max_length=150)
    senha: str = Field(min_length=8, max_length=128)
    telefone: str | None = Field(default=None, max_length=20)
    foto_perfil: str | None = Field(default=None, max_length=255)
    cargo: CargoUsuario = CargoUsuario.FUNCIONARIO


class UsuarioUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=150)
    email: str | None = Field(default=None, min_length=3, max_length=150)
    telefone: str | None = Field(default=None, max_length=20)
    foto_perfil: str | None = Field(default=None, max_length=255)
    cargo: CargoUsuario | None = None
    ativo: bool | None = None


class UsuarioOut(ORMModel):
    id: int
    empresa_id: int
    nome: str
    email: str
    telefone: str | None
    foto_perfil: str | None
    cargo: CargoUsuario
    ativo: bool
    ultimo_login: datetime | None
    created_at: datetime


class ClienteCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    telefone: str | None = Field(default=None, max_length=20)
    whatsapp: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=150)
    cpf: str | None = Field(default=None, max_length=14)
    data_nascimento: date | None = None
    observacoes: str | None = None


class ClienteUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=150)
    telefone: str | None = Field(default=None, max_length=20)
    whatsapp: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=150)
    cpf: str | None = Field(default=None, max_length=14)
    data_nascimento: date | None = None
    status: StatusCliente | None = None
    ultima_visita: datetime | None = None
    observacoes: str | None = None


class ClienteOut(ORMModel):
    id: int
    empresa_id: int
    nome: str
    telefone: str | None
    whatsapp: str | None
    email: str | None
    cpf: str | None
    data_nascimento: date | None
    status: StatusCliente
    ultima_visita: datetime | None
    observacoes: str | None
    created_at: datetime


class VeiculoCreate(BaseModel):
    cliente_id: int = Field(gt=0)
    tipo_veiculo: TipoVeiculo | None = None
    marca: str | None = Field(default=None, max_length=80)
    modelo: str | None = Field(default=None, max_length=80)
    ano: int | None = Field(default=None, ge=1900, le=2100)
    placa: str | None = Field(default=None, max_length=10)
    cor: str | None = Field(default=None, max_length=40)
    apelido: str | None = Field(default=None, max_length=80)
    quilometragem: int | None = Field(default=None, ge=0)
    observacoes: str | None = None


class VeiculoUpdate(BaseModel):
    tipo_veiculo: TipoVeiculo | None = None
    marca: str | None = Field(default=None, max_length=80)
    modelo: str | None = Field(default=None, max_length=80)
    ano: int | None = Field(default=None, ge=1900, le=2100)
    placa: str | None = Field(default=None, max_length=10)
    cor: str | None = Field(default=None, max_length=40)
    apelido: str | None = Field(default=None, max_length=80)
    quilometragem: int | None = Field(default=None, ge=0)
    observacoes: str | None = None


class VeiculoOut(ORMModel):
    id: int
    cliente_id: int
    tipo_veiculo: TipoVeiculo | None
    marca: str | None
    modelo: str | None
    ano: int | None
    placa: str | None
    cor: str | None
    apelido: str | None
    quilometragem: int | None
    observacoes: str | None
    created_at: datetime


class ServicoAdicionalInput(BaseModel):
    tipo_veiculo: TipoVeiculo
    valor_adicional: Decimal = Field(ge=0, le=99999999)


class ServicoAdicionalOut(ORMModel):
    tipo_veiculo: TipoVeiculo
    valor_adicional: Decimal


class ServicoCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    descricao: str | None = None
    duracao_minutos: int = Field(gt=0, le=1440)
    preco: Decimal = Field(ge=0)
    cor_agenda: str | None = Field(default=None, max_length=7)
    adicional_por_tipo_ativo: bool = False
    adicionais: list[ServicoAdicionalInput] = Field(default_factory=list)


class ServicoUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=150)
    descricao: str | None = None
    duracao_minutos: int | None = Field(default=None, gt=0, le=1440)
    preco: Decimal | None = Field(default=None, ge=0)
    cor_agenda: str | None = Field(default=None, max_length=7)
    ativo: bool | None = None
    adicional_por_tipo_ativo: bool | None = None
    adicionais: list[ServicoAdicionalInput] | None = None


class ServicoOut(ORMModel):
    id: int
    empresa_id: int
    nome: str
    descricao: str | None
    duracao_minutos: int
    preco: Decimal
    cor_agenda: str | None
    ativo: bool
    adicional_por_tipo_ativo: bool
    adicionais: list[ServicoAdicionalOut]


class AgendamentoCreate(BaseModel):
    cliente_id: int = Field(gt=0)
    veiculo_id: int | None = Field(default=None, gt=0)
    tipo_veiculo: TipoVeiculo | None = None
    servico_id: int = Field(gt=0)
    funcionario_id: int | None = Field(default=None, gt=0)
    data: date
    hora_inicio: time
    hora_fim: time | None = None
    status: StatusAgendamento = StatusAgendamento.PENDENTE
    origem: OrigemAgendamento = OrigemAgendamento.FUNCIONARIO
    valor_final: Decimal | None = Field(default=None, ge=0)
    forma_pagamento: FormaPagamento | None = None
    observacoes: str | None = None


class AgendamentoUpdate(BaseModel):
    veiculo_id: int | None = Field(default=None, gt=0)
    tipo_veiculo: TipoVeiculo | None = None
    servico_id: int | None = Field(default=None, gt=0)
    funcionario_id: int | None = Field(default=None, gt=0)
    data: date | None = None
    hora_inicio: time | None = None
    hora_fim: time | None = None
    status: StatusAgendamento | None = None
    valor_final: Decimal | None = Field(default=None, ge=0)
    forma_pagamento: FormaPagamento | None = None
    observacoes: str | None = None


class AgendamentoOut(ORMModel):
    id: int
    empresa_id: int
    cliente_id: int
    veiculo_id: int | None
    servico_id: int
    funcionario_id: int | None
    data: date
    hora_inicio: time
    hora_fim: time
    status: StatusAgendamento
    origem: OrigemAgendamento
    valor_base: Decimal
    valor_adicional: Decimal
    valor_final: Decimal | None
    tipo_veiculo_cobrado: TipoVeiculo | None
    forma_pagamento: FormaPagamento | None
    confirmado_em: datetime | None
    cancelado_em: datetime | None
    finalizado_em: datetime | None
    observacoes: str | None
    created_at: datetime


class HorarioCreate(BaseModel):
    funcionario_id: int = Field(gt=0)
    dia_semana: int = Field(ge=0, le=6)
    hora_inicio: time
    hora_fim: time
    pausa_inicio: time | None = None
    pausa_fim: time | None = None
    ativo: bool = True


class HorarioUpdate(BaseModel):
    dia_semana: int | None = Field(default=None, ge=0, le=6)
    hora_inicio: time | None = None
    hora_fim: time | None = None
    pausa_inicio: time | None = None
    pausa_fim: time | None = None
    ativo: bool | None = None


class HorarioOut(ORMModel):
    id: int
    empresa_id: int
    funcionario_id: int
    dia_semana: int
    hora_inicio: time
    hora_fim: time
    pausa_inicio: time | None
    pausa_fim: time | None
    ativo: bool


class BloqueioCreate(BaseModel):
    funcionario_id: int | None = Field(default=None, gt=0)
    data_inicio: date
    data_fim: date
    hora_inicio: time | None = None
    hora_fim: time | None = None
    motivo: str | None = Field(default=None, max_length=150)


class BloqueioOut(ORMModel):
    id: int
    empresa_id: int
    funcionario_id: int | None
    data_inicio: date
    data_fim: date
    hora_inicio: time | None
    hora_fim: time | None
    motivo: str | None
    created_at: datetime


class ConversaCreate(BaseModel):
    cliente_id: int = Field(gt=0)
    responsavel_id: int | None = Field(default=None, gt=0)
    origem: OrigemConversa = OrigemConversa.WHATSAPP


class ConversaUpdate(BaseModel):
    responsavel_id: int | None = Field(default=None, gt=0)
    status: StatusConversa | None = None
    ia_ativa: bool | None = None


class ConversaFinalizar(BaseModel):
    resumo_finalizacao: str | None = Field(default=None, max_length=1500)
    enviar_avaliacao: bool = True


class ConversaAvaliacaoResposta(BaseModel):
    nota: int = Field(ge=1, le=5)
    comentario: str | None = Field(default=None, max_length=1500)


class ConversaOut(ORMModel):
    id: int
    empresa_id: int
    cliente_id: int
    responsavel_id: int | None
    status: StatusConversa
    origem: OrigemConversa
    ia_ativa: bool
    ultima_mensagem_id: int | None
    ultima_interacao: datetime | None
    finalizada_em: datetime | None
    finalizada_por_id: int | None
    resumo_finalizacao: str | None
    avaliacao_solicitada: bool
    avaliacao_enviada_em: datetime | None
    avaliacao_nota: int | None
    avaliacao_comentario: str | None
    avaliacao_respondida_em: datetime | None
    created_at: datetime


class MensagemCreate(BaseModel):
    remetente: RemetenteMensagem
    conteudo: str = Field(min_length=1)
    tipo: TipoMensagem = TipoMensagem.TEXTO
    arquivo_url: str | None = Field(default=None, max_length=255)
    id_whatsapp: str | None = Field(default=None, max_length=100)


class MensagemOut(ORMModel):
    id: int
    conversa_id: int
    remetente: RemetenteMensagem
    conteudo: str
    tipo: TipoMensagem
    arquivo_url: str | None
    id_whatsapp: str | None
    lida: bool
    data_envio: datetime


class ConfigIAPut(BaseModel):
    nome_assistente: str = Field(default="Assistente", min_length=1, max_length=80)
    mensagem_boas_vindas: str | None = None
    prompt: str | None = None
    temperatura: Decimal = Field(default=Decimal("0.70"), ge=0, le=2)


class ConfigIAOut(ORMModel):
    id: int
    empresa_id: int
    nome_assistente: str
    mensagem_boas_vindas: str | None
    prompt: str | None
    temperatura: Decimal


class MemoriaCreate(BaseModel):
    cliente_id: int = Field(gt=0)
    categoria: str | None = Field(default=None, max_length=60)
    informacao: str = Field(min_length=1)


class MemoriaUpdate(BaseModel):
    categoria: str | None = Field(default=None, max_length=60)
    informacao: str | None = Field(default=None, min_length=1)


class MemoriaOut(ORMModel):
    id: int
    empresa_id: int
    cliente_id: int
    categoria: str | None
    informacao: str
    created_at: datetime
    updated_at: datetime


class IntegracaoCreate(BaseModel):
    tipo: TipoIntegracao
    nome: str | None = Field(default=None, max_length=100)
    ativo: bool = True
    identificador: str | None = Field(default=None, max_length=150)
    token: str | None = None
    configuracoes: dict[str, Any] | None = None


class IntegracaoUpdate(BaseModel):
    nome: str | None = Field(default=None, max_length=100)
    ativo: bool | None = None
    identificador: str | None = Field(default=None, max_length=150)
    token: str | None = None
    configuracoes: dict[str, Any] | None = None


class IntegracaoOut(ORMModel):
    id: int
    empresa_id: int
    tipo: TipoIntegracao
    nome: str | None
    ativo: bool
    identificador: str | None
    configuracoes: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class NotificacaoOut(ORMModel):
    id: int
    empresa_id: int
    usuario_id: int | None
    titulo: str
    mensagem: str
    lida: bool
    created_at: datetime


class PlanoOut(ORMModel):
    id: int
    nome: str
    descricao: str | None
    preco: Decimal
    ativo: bool
    created_at: datetime


class AssinaturaOut(ORMModel):
    id: int
    empresa_id: int
    plano_id: int
    forma_pagamento: FormaPagamento | None
    status: StatusAssinatura
    data_inicio: date
    data_vencimento: date | None
    created_at: datetime


class LogOut(ORMModel):
    id: int
    empresa_id: int
    ator_tipo: str
    ator_id: int | None
    acao: str
    entidade: str | None
    entidade_id: int | None
    detalhes: dict[str, Any] | None
    created_at: datetime


class DashboardOut(BaseModel):
    agendamentos_hoje: int
    agendamentos_pendentes: int
    conversas_abertas: int
    clientes_ativos: int
    notificacoes_nao_lidas: int


class SlotDisponivel(BaseModel):
    hora_inicio: time
    hora_fim: time
