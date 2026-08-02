from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class ConfiguracaoAgenda(Base):
    __tablename__ = "configuracoes_agenda"

    empresa_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("empresas.id", ondelete="CASCADE"),
        primary_key=True,
    )
    intervalo_minutos: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
        server_default=text("30"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=text("NOW()"),
    )
