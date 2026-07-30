from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class FechamentoFinanceiro(Base):
    __tablename__ = "fechamentos_financeiros"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id",
            "agendamento_id",
            name="uq_fechamento_empresa_agendamento",
        ),
        CheckConstraint(
            "status IN ('PENDENTE', 'PARCIAL', 'PAGO', 'CORTESIA', 'ESTORNADO')",
            name="ck_fechamento_status",
        ),
        CheckConstraint(
            "desconto_tipo IS NULL OR desconto_tipo IN ('VALOR', 'PERCENTUAL')",
            name="ck_fechamento_desconto_tipo",
        ),
        CheckConstraint(
            "valor_original >= 0 AND desconto_valor >= 0 AND valor_final >= 0 "
            "AND valor_recebido >= 0 AND valor_pendente >= 0",
            name="ck_fechamento_valores_nao_negativos",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    empresa_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("empresas.id", ondelete="CASCADE"),
        nullable=False,
    )
    agendamento_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("agendamentos.id", ondelete="CASCADE"),
        nullable=False,
    )
    valor_original: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    desconto_tipo: Mapped[str | None] = mapped_column(String(20))
    desconto_valor: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    valor_final: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    valor_recebido: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    valor_pendente: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDENTE",
    )
    observacoes: Mapped[str | None] = mapped_column(Text)
    fechado_por_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("usuarios.id", ondelete="SET NULL"),
    )
    atualizado_por_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("usuarios.id", ondelete="SET NULL"),
    )
    fechado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    pagamentos: Mapped[list["PagamentoAtendimento"]] = relationship(
        "PagamentoAtendimento",
        back_populates="fechamento",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PagamentoAtendimento.created_at",
    )


class PagamentoAtendimento(Base):
    __tablename__ = "pagamentos_atendimento"
    __table_args__ = (
        CheckConstraint(
            "status IN ('CONFIRMADO', 'ESTORNADO')",
            name="ck_pagamento_atendimento_status",
        ),
        CheckConstraint(
            "valor > 0",
            name="ck_pagamento_atendimento_valor_positivo",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    empresa_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("empresas.id", ondelete="CASCADE"),
        nullable=False,
    )
    fechamento_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("fechamentos_financeiros.id", ondelete="CASCADE"),
        nullable=False,
    )
    forma_pagamento: Mapped[str] = mapped_column(String(30), nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="CONFIRMADO",
    )
    recebido_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    registrado_por_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("usuarios.id", ondelete="SET NULL"),
    )
    observacoes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    fechamento: Mapped[FechamentoFinanceiro] = relationship(
        "FechamentoFinanceiro",
        back_populates="pagamentos",
    )


@event.listens_for(FechamentoFinanceiro, "before_insert")
@event.listens_for(FechamentoFinanceiro, "before_update")
def normalizar_desconto_percentual(
    _mapper: object,
    _connection: object,
    target: FechamentoFinanceiro,
) -> None:
    """Mantém no banco o valor monetário efetivamente descontado.

    A API aceita porcentagem como entrada, calcula o abatimento e normaliza o tipo
    para VALOR antes de persistir. Assim pagamentos posteriores e estornos nunca
    reinterpretam um valor em reais como se ainda fosse percentual.
    """
    if target.desconto_tipo == "PERCENTUAL":
        target.desconto_tipo = "VALOR"
