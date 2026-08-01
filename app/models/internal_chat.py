from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class CanalChatInterno(Base):
    __tablename__ = "canais_chat_interno"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("empresas.id", ondelete="CASCADE"),
        nullable=False,
    )
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    nome: Mapped[str | None] = mapped_column(String(100))
    criado_por_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("usuarios.id", ondelete="SET NULL"),
    )
    chave_unica: Mapped[str | None] = mapped_column(
        String(160),
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )


class MembroCanalChatInterno(Base):
    __tablename__ = "membros_canais_chat_interno"
    __table_args__ = (
        UniqueConstraint(
            "canal_id",
            "usuario_id",
            name="uq_membro_canal_chat_interno",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    canal_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("canais_chat_interno.id", ondelete="CASCADE"),
        nullable=False,
    )
    usuario_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )


class MensagemChatInterno(Base):
    __tablename__ = "mensagens_canais_chat_interno"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    canal_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("canais_chat_interno.id", ondelete="CASCADE"),
        nullable=False,
    )
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
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)
    legacy_mensagem_id: Mapped[int | None] = mapped_column(
        BigInteger,
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )


class LeituraChatInterno(Base):
    __tablename__ = "leituras_canais_chat_interno"
    __table_args__ = (
        UniqueConstraint(
            "canal_id",
            "usuario_id",
            name="uq_leitura_canal_chat_interno_usuario",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    canal_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("canais_chat_interno.id", ondelete="CASCADE"),
        nullable=False,
    )
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
    ultima_mensagem_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
