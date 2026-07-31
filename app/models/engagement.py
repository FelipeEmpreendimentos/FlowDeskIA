from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class EmpresaOnboarding(Base):
    __tablename__ = "empresa_onboarding"
    __table_args__ = (
        UniqueConstraint("empresa_id", name="uq_empresa_onboarding_empresa"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    empresa_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("empresas.id", ondelete="CASCADE"),
        nullable=False,
    )
    oculto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )


class PreferenciaNotificacao(Base):
    __tablename__ = "preferencias_notificacao"
    __table_args__ = (
        UniqueConstraint("usuario_id", name="uq_preferencia_notificacao_usuario"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    empresa_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("empresas.id", ondelete="CASCADE"),
        nullable=False,
    )
    usuario_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    agendamentos: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    financeiro: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    conversas: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    avaliacoes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    integracoes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    planos_limites: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sistema: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
