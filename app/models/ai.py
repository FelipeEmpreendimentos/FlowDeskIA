from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, SmallInteger, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


DEFAULT_AI_MENU = [
    {"acao": "AGENDAR", "rotulo": "Agendar serviço", "ativo": True, "ordem": 10},
    {"acao": "CONSULTAR_AGENDAMENTO", "rotulo": "Consultar agendamento", "ativo": True, "ordem": 20},
    {"acao": "REAGENDAR", "rotulo": "Reagendar", "ativo": True, "ordem": 30},
    {"acao": "CANCELAR", "rotulo": "Cancelar", "ativo": True, "ordem": 40},
    {"acao": "SERVICOS_PRECOS", "rotulo": "Serviços e preços", "ativo": True, "ordem": 50},
    {"acao": "HUMANO", "rotulo": "Falar com atendente", "ativo": True, "ordem": 60},
]


class AICompanySettings(Base):
    __tablename__ = "ai_company_settings"

    empresa_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("empresas.id", ondelete="CASCADE"),
        primary_key=True,
    )
    saudacao_cliente_novo: Mapped[str | None] = mapped_column(Text)
    saudacao_cliente_conhecido: Mapped[str | None] = mapped_column(Text)
    mensagem_transferencia: Mapped[str | None] = mapped_column(Text)
    mensagem_fora_escopo: Mapped[str | None] = mapped_column(Text)
    mensagem_indisponibilidade: Mapped[str | None] = mapped_column(Text)
    mensagem_despedida: Mapped[str | None] = mapped_column(Text)
    texto_menu_principal: Mapped[str | None] = mapped_column(Text)
    tom: Mapped[str] = mapped_column(String(20), nullable=False, default="EQUILIBRADO")
    tamanho_resposta: Mapped[str] = mapped_column(String(20), nullable=False, default="CURTA")
    usar_emojis: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criar_cliente_auto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criar_veiculo_auto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    pode_agendar: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    pode_reagendar: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    pode_cancelar: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    confirmar_acoes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    transferir_fora_escopo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fluxo_guiado_ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    mostrar_interpretacao: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tentativas_antes_handoff: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=2)
    campos_cliente_obrigatorios: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: ["nome"],
    )
    campos_veiculo_obrigatorios: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: ["tipo_veiculo"],
    )
    conhecimento: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    menu_principal: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: [dict(item) for item in DEFAULT_AI_MENU],
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )


class AIContactMetadata(Base):
    __tablename__ = "ai_contact_metadata"

    cliente_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clientes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    empresa_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("empresas.id", ondelete="CASCADE"),
        nullable=False,
    )
    criado_por_ia: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    origem: Mapped[str] = mapped_column(String(40), nullable=False, default="IA")
    cadastro_completo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class AIVehicleMetadata(Base):
    __tablename__ = "ai_vehicle_metadata"

    veiculo_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("veiculos.id", ondelete="CASCADE"),
        primary_key=True,
    )
    empresa_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("empresas.id", ondelete="CASCADE"),
        nullable=False,
    )
    criado_por_ia: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    origem: Mapped[str] = mapped_column(String(40), nullable=False, default="IA")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class AIAttendanceSession(Base):
    __tablename__ = "ai_atendimento_sessoes"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id",
            "canal",
            "external_id",
            name="uq_ai_atendimento_empresa_canal_external",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("empresas.id", ondelete="CASCADE"),
        nullable=False,
    )
    canal: Mapped[str] = mapped_column(String(30), nullable=False, default="WHATSAPP")
    external_id: Mapped[str] = mapped_column(String(150), nullable=False)
    cliente_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("clientes.id", ondelete="SET NULL"),
    )
    estado: Mapped[str] = mapped_column(String(30), nullable=False, default="ATENDENDO")
    falhas_entendimento: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    pending_action: Mapped[dict | None] = mapped_column(JSONB)
    flow_context: Mapped[dict | None] = mapped_column(JSONB)
    last_intent: Mapped[str | None] = mapped_column(String(80))
    last_tool_trace: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    handoff_motivo: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
