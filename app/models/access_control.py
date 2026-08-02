from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class EmpresaModulo(Base):
    __tablename__ = "empresa_modulos"
    __table_args__ = (
        UniqueConstraint("empresa_id", "modulo", name="uq_empresa_modulo"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("empresas.id", ondelete="CASCADE"),
        nullable=False,
    )
    modulo: Mapped[str] = mapped_column(String(40), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class UsuarioPermissaoModulo(Base):
    __tablename__ = "usuario_permissoes_modulo"
    __table_args__ = (
        UniqueConstraint("usuario_id", "modulo", name="uq_usuario_permissao_modulo"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
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
    modulo: Mapped[str] = mapped_column(String(40), nullable=False)
    permitido: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
