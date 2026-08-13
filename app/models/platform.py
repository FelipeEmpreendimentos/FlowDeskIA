from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    event,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class PlanoConfiguracao(Base):
    __tablename__ = "plano_configuracoes"

    plano_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("planos.id", ondelete="CASCADE"),
        primary_key=True,
    )
    codigo: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    preco_anual: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    periodo_teste_dias: Mapped[int] = mapped_column(
        Integer, nullable=False, default=14
    )
    limite_usuarios: Mapped[int | None] = mapped_column(Integer)
    limite_clientes: Mapped[int | None] = mapped_column(Integer)
    limite_agendamentos_mes: Mapped[int | None] = mapped_column(Integer)
    limite_conversas_mes: Mapped[int | None] = mapped_column(Integer)
    limite_mensagens_ia_mes: Mapped[int | None] = mapped_column(Integer)
    limite_canais: Mapped[int | None] = mapped_column(Integer)
    limite_armazenamento_mb: Mapped[int | None] = mapped_column(Integer)
    ia_incluida: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    ia_adicional_disponivel: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    recursos: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )


@event.listens_for(PlanoConfiguracao, "before_insert")
@event.listens_for(PlanoConfiguracao, "before_update")
def normalize_included_ai_for_plan(_mapper, _connection, target: PlanoConfiguracao) -> None:
    if target.codigo in {"ESSENCIAL", "PROFISSIONAL"}:
        target.ia_incluida = False


class EmpresaPlataforma(Base):
    __tablename__ = "empresa_plataforma"

    empresa_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("empresas.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="TRIAL"
    )
    trial_fim: Mapped[date | None] = mapped_column(Date)
    recursos_personalizados: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    limites_personalizados: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    ia_adicional_ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    ia_limite_adicional: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    observacoes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )


class SuperAdmin(Base):
    __tablename__ = "super_admins"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    dois_fatores_ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    ultimo_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class SuperAdminLog(Base):
    __tablename__ = "super_admin_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    super_admin_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("super_admins.id", ondelete="SET NULL"),
    )
    empresa_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("empresas.id", ondelete="SET NULL"),
    )
    acao: Mapped[str] = mapped_column(String(100), nullable=False)
    entidade: Mapped[str | None] = mapped_column(String(60))
    entidade_id: Mapped[int | None] = mapped_column(BigInteger)
    dados_anteriores: Mapped[dict | None] = mapped_column(JSONB)
    dados_novos: Mapped[dict | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
