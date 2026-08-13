from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class RelatorioResumoOut(BaseModel):
    data_inicio: date
    data_fim: date
    usar_financeiro: bool
    atendimentos: int
    faturamento: Decimal
    recebido: Decimal
    pendente: Decimal
    descontos: Decimal
    ticket_medio: Decimal
    cancelamentos: int
    clientes_novos: int
    clientes_recorrentes: int


class RelatorioEvolucaoItem(BaseModel):
    data: date
    atendimentos: int
    faturamento: Decimal
    recebido: Decimal
    pendente: Decimal


class RelatorioServicoItem(BaseModel):
    servico_id: int
    servico_nome: str
    atendimentos: int
    faturamento: Decimal
    recebido: Decimal
    ticket_medio: Decimal


class RelatorioFuncionarioItem(BaseModel):
    funcionario_id: int | None
    funcionario_nome: str
    atendimentos: int
    faturamento: Decimal
    recebido: Decimal
    ticket_medio: Decimal


class AvaliacaoComentarioItem(BaseModel):
    conversa_id: int
    cliente_id: int
    cliente_nome: str
    funcionario_id: int | None
    funcionario_nome: str | None
    nota: int
    comentario: str | None
    respondida_em: datetime | None


class RelatorioAvaliacoesOut(BaseModel):
    quantidade: int
    media: Decimal
    notas: dict[int, int]
    avaliacoes_baixas: int
    comentarios: list[AvaliacaoComentarioItem]


class PlanoConsumoItem(BaseModel):
    chave: str
    nome: str
    utilizado: int
    limite: int | None


class PlanoEmpresaOut(BaseModel):
    plano_id: int | None
    plano_nome: str | None
    descricao: str | None
    preco_mensal: Decimal | None
    preco_anual: Decimal | None
    status_empresa: str | None
    status_assinatura: str | None
    trial_fim: date | None
    data_inicio: date | None
    data_vencimento: date | None
    ia_ativa: bool
    ia_adicional_ativo: bool
    recursos: dict[str, bool]
    consumo: list[PlanoConsumoItem]


class AtividadeOut(BaseModel):
    id: int
    usuario_id: int | None
    usuario_nome: str | None
    usuario_cargo: str | None
    acao: str
    entidade: str | None
    entidade_id: int | None
    descricao: str
    detalhes: dict[str, Any] | None
    created_at: datetime
