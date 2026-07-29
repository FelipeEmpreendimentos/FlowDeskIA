from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.models.enums import (
    AtorLog,
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


def pg_enum(enum_class: type, name: str) -> PGEnum:
    return PGEnum(
        enum_class,
        name=name,
        create_type=False,
        values_callable=lambda members: [member.value for member in members],
    )


class Plano(Base):
    __tablename__ = "planos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nome: Mapped[str] = mapped_column(String(60), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    preco: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class Empresa(Base):
    __tablename__ = "empresas"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    cnpj: Mapped[str] = mapped_column(String(18), nullable=False, unique=True)
    telefone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(150))
    plano_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("planos.id", ondelete="SET NULL")
    )
    logo: Mapped[str | None] = mapped_column(String(255))
    cidade: Mapped[str | None] = mapped_column(String(100))
    estado: Mapped[str | None] = mapped_column(String(2))
    timezone: Mapped[str] = mapped_column(
        String(50), nullable=False, default="America/Sao_Paulo"
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    horario_abertura: Mapped[time | None] = mapped_column(Time)
    horario_fechamento: Mapped[time | None] = mapped_column(Time)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class Assinatura(Base):
    __tablename__ = "assinaturas"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    plano_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("planos.id", ondelete="RESTRICT"), nullable=False
    )
    forma_pagamento: Mapped[FormaPagamento | None] = mapped_column(
        pg_enum(FormaPagamento, "forma_pagamento")
    )
    status: Mapped[StatusAssinatura] = mapped_column(
        pg_enum(StatusAssinatura, "status_assinatura"),
        nullable=False,
        default=StatusAssinatura.TRIAL,
    )
    data_inicio: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=text("CURRENT_DATE")
    )
    data_vencimento: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    telefone: Mapped[str | None] = mapped_column(String(20))
    foto_perfil: Mapped[str | None] = mapped_column(String(255))
    cargo: Mapped[CargoUsuario] = mapped_column(
        pg_enum(CargoUsuario, "cargo_usuario"),
        nullable=False,
        default=CargoUsuario.FUNCIONARIO,
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ultimo_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    telefone: Mapped[str | None] = mapped_column(String(20))
    whatsapp: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(150))
    cpf: Mapped[str | None] = mapped_column(String(14))
    data_nascimento: Mapped[date | None] = mapped_column(Date)
    status: Mapped[StatusCliente] = mapped_column(
        pg_enum(StatusCliente, "status_cliente"),
        nullable=False,
        default=StatusCliente.ATIVO,
    )
    ultima_visita: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    observacoes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class Veiculo(Base):
    __tablename__ = "veiculos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False
    )
    tipo_veiculo: Mapped[str | None] = mapped_column(String(20))
    marca: Mapped[str | None] = mapped_column(String(80))
    modelo: Mapped[str | None] = mapped_column(String(80))
    ano: Mapped[int | None] = mapped_column(SmallInteger)
    placa: Mapped[str | None] = mapped_column(String(10))
    cor: Mapped[str | None] = mapped_column(String(40))
    apelido: Mapped[str | None] = mapped_column(String(80))
    quilometragem: Mapped[int | None] = mapped_column(Integer)
    observacoes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class Servico(Base):
    __tablename__ = "servicos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    duracao_minutos: Mapped[int] = mapped_column(Integer, nullable=False)
    preco: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    cor_agenda: Mapped[str | None] = mapped_column(String(7))
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    adicional_por_tipo_ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    adicionais: Mapped[list["ServicoAdicionalVeiculo"]] = relationship(
        "ServicoAdicionalVeiculo",
        back_populates="servico",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ServicoAdicionalVeiculo.tipo_veiculo",
    )


class ServicoAdicionalVeiculo(Base):
    __tablename__ = "servico_adicionais_veiculo"
    __table_args__ = (
        UniqueConstraint(
            "servico_id",
            "tipo_veiculo",
            name="uq_servico_adicional_tipo_veiculo",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    servico_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("servicos.id", ondelete="CASCADE"),
        nullable=False,
    )
    tipo_veiculo: Mapped[str] = mapped_column(String(20), nullable=False)
    valor_adicional: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    servico: Mapped[Servico] = relationship(
        "Servico", back_populates="adicionais"
    )


class Agendamento(Base):
    __tablename__ = "agendamentos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    cliente_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False
    )
    veiculo_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("veiculos.id", ondelete="SET NULL")
    )
    servico_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("servicos.id", ondelete="RESTRICT"), nullable=False
    )
    funcionario_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    data: Mapped[date] = mapped_column(Date, nullable=False)
    hora_inicio: Mapped[time] = mapped_column(Time, nullable=False)
    hora_fim: Mapped[time] = mapped_column(Time, nullable=False)
    status: Mapped[StatusAgendamento] = mapped_column(
        pg_enum(StatusAgendamento, "status_agendamento"),
        nullable=False,
        default=StatusAgendamento.PENDENTE,
    )
    origem: Mapped[OrigemAgendamento] = mapped_column(
        pg_enum(OrigemAgendamento, "origem_agendamento"),
        nullable=False,
        default=OrigemAgendamento.WHATSAPP,
    )
    valor_base: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    valor_adicional: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    valor_final: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    tipo_veiculo_cobrado: Mapped[str | None] = mapped_column(String(20))
    forma_pagamento: Mapped[FormaPagamento | None] = mapped_column(
        pg_enum(FormaPagamento, "forma_pagamento")
    )
    confirmado_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    cancelado_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    finalizado_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    observacoes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class Conversa(Base):
    __tablename__ = "conversas"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    cliente_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False
    )
    responsavel_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    status: Mapped[StatusConversa] = mapped_column(
        pg_enum(StatusConversa, "status_conversa"),
        nullable=False,
        default=StatusConversa.ABERTA,
    )
    origem: Mapped[OrigemConversa] = mapped_column(
        pg_enum(OrigemConversa, "origem_conversa"),
        nullable=False,
        default=OrigemConversa.WHATSAPP,
    )
    ia_ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ultima_mensagem_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("mensagens.id", ondelete="SET NULL")
    )
    ultima_interacao: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    finalizada_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    finalizada_por_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    resumo_finalizacao: Mapped[str | None] = mapped_column(Text)
    avaliacao_solicitada: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    avaliacao_token: Mapped[str | None] = mapped_column(
        String(36), unique=True
    )
    avaliacao_enviada_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    avaliacao_nota: Mapped[int | None] = mapped_column(SmallInteger)
    avaliacao_comentario: Mapped[str | None] = mapped_column(Text)
    avaliacao_respondida_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class Mensagem(Base):
    __tablename__ = "mensagens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conversa_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("conversas.id", ondelete="CASCADE"), nullable=False
    )
    remetente: Mapped[RemetenteMensagem] = mapped_column(
        pg_enum(RemetenteMensagem, "remetente_mensagem"),
        nullable=False,
    )
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[TipoMensagem] = mapped_column(
        pg_enum(TipoMensagem, "tipo_mensagem"),
        nullable=False,
        default=TipoMensagem.TEXTO,
    )
    arquivo_url: Mapped[str | None] = mapped_column(String(255))
    id_whatsapp: Mapped[str | None] = mapped_column(String(100))
    lida: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    data_envio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class Horario(Base):
    __tablename__ = "horarios"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    funcionario_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    dia_semana: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    hora_inicio: Mapped[time] = mapped_column(Time, nullable=False)
    hora_fim: Mapped[time] = mapped_column(Time, nullable=False)
    pausa_inicio: Mapped[time | None] = mapped_column(Time)
    pausa_fim: Mapped[time | None] = mapped_column(Time)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class BloqueioAgenda(Base):
    __tablename__ = "bloqueios_agenda"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    funcionario_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("usuarios.id", ondelete="CASCADE")
    )
    data_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    data_fim: Mapped[date] = mapped_column(Date, nullable=False)
    hora_inicio: Mapped[time | None] = mapped_column(Time)
    hora_fim: Mapped[time | None] = mapped_column(Time)
    motivo: Mapped[str | None] = mapped_column(String(150))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class ConfigIA(Base):
    __tablename__ = "config_ia"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("empresas.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    nome_assistente: Mapped[str] = mapped_column(
        String(80), nullable=False, default="Assistente"
    )
    mensagem_boas_vindas: Mapped[str | None] = mapped_column(Text)
    prompt: Mapped[str | None] = mapped_column(Text)
    temperatura: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, default=Decimal("0.70")
    )


class MemoriaIA(Base):
    __tablename__ = "memoria_ia"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    cliente_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False
    )
    categoria: Mapped[str | None] = mapped_column(String(60))
    informacao: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class Log(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    ator_tipo: Mapped[AtorLog] = mapped_column(
        pg_enum(AtorLog, "ator_log"), nullable=False
    )
    ator_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    acao: Mapped[str] = mapped_column(String(100), nullable=False)
    entidade: Mapped[str | None] = mapped_column(String(50))
    entidade_id: Mapped[int | None] = mapped_column(BigInteger)
    detalhes: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class Integracao(Base):
    __tablename__ = "integracoes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[TipoIntegracao] = mapped_column(
        pg_enum(TipoIntegracao, "tipo_integracao"), nullable=False
    )
    nome: Mapped[str | None] = mapped_column(String(100))
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    identificador: Mapped[str | None] = mapped_column(String(150))
    token: Mapped[str | None] = mapped_column(Text)
    configuracoes: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class Notificacao(Base):
    __tablename__ = "notificacoes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    usuario_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("usuarios.id", ondelete="CASCADE")
    )
    titulo: Mapped[str] = mapped_column(String(150), nullable=False)
    mensagem: Mapped[str] = mapped_column(Text, nullable=False)
    lida: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
