from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import FormaPagamento
from app.schemas.common import ORMModel


StatusFechamento = Literal["PENDENTE", "PARCIAL", "PAGO", "CORTESIA", "ESTORNADO"]
TipoDesconto = Literal["VALOR", "PERCENTUAL"]


class PagamentoInput(BaseModel):
    forma_pagamento: FormaPagamento
    valor: Decimal = Field(gt=0, le=999999999)
    recebido_em: datetime | None = None
    observacoes: str | None = Field(default=None, max_length=1000)


class FechamentoSalvar(BaseModel):
    desconto_tipo: TipoDesconto | None = None
    desconto_valor: Decimal = Field(default=Decimal("0.00"), ge=0)
    cortesia: bool = False
    observacoes: str | None = Field(default=None, max_length=2000)
    pagamentos: list[PagamentoInput] = Field(default_factory=list)


class FechamentoAtualizar(BaseModel):
    desconto_tipo: TipoDesconto | None = None
    desconto_valor: Decimal = Field(default=Decimal("0.00"), ge=0)
    cortesia: bool = False
    observacoes: str | None = Field(default=None, max_length=2000)


class PagamentoOut(ORMModel):
    id: int
    empresa_id: int
    fechamento_id: int
    forma_pagamento: FormaPagamento
    valor: Decimal
    status: Literal["CONFIRMADO", "ESTORNADO"]
    recebido_em: datetime
    registrado_por_id: int | None
    observacoes: str | None
    created_at: datetime


class FechamentoOut(ORMModel):
    id: int
    empresa_id: int
    agendamento_id: int
    valor_original: Decimal
    desconto_tipo: TipoDesconto | None
    desconto_valor: Decimal
    valor_final: Decimal
    valor_recebido: Decimal
    valor_pendente: Decimal
    status: StatusFechamento
    observacoes: str | None
    fechado_por_id: int | None
    atualizado_por_id: int | None
    fechado_em: datetime | None
    created_at: datetime
    updated_at: datetime
    pagamentos: list[PagamentoOut]


class FechamentoListaItem(BaseModel):
    id: int
    agendamento_id: int
    data: date
    hora_inicio: str
    cliente_id: int
    cliente_nome: str
    servico_id: int
    servico_nome: str
    funcionario_id: int | None
    funcionario_nome: str | None
    valor_original: Decimal
    desconto_valor: Decimal
    valor_final: Decimal
    valor_recebido: Decimal
    valor_pendente: Decimal
    status: StatusFechamento
    forma_pagamento_principal: FormaPagamento | None
    fechado_em: datetime | None


class ResumoFinanceiroOut(BaseModel):
    quantidade: int
    valor_original: Decimal
    descontos: Decimal
    valor_final: Decimal
    valor_recebido: Decimal
    valor_pendente: Decimal
    pendentes: int
    parciais: int
    pagos: int
    cortesias: int
