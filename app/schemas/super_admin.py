from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


StatusPlataforma = Literal["TRIAL", "ATIVA", "SUSPENSA", "CANCELADA", "ARQUIVADA"]


class SuperAdminLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=150)
    senha: str = Field(min_length=8, max_length=128)


class SuperAdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class SuperAdminOut(ORMModel):
    id: int
    nome: str
    email: str
    ativo: bool
    dois_fatores_ativo: bool
    ultimo_login: datetime | None
    created_at: datetime


class SuperAdminAlterarSenhaRequest(BaseModel):
    senha_atual: str = Field(min_length=8, max_length=128)
    nova_senha: str = Field(min_length=8, max_length=128)


class PlanoBase(BaseModel):
    nome: str = Field(min_length=2, max_length=60)
    descricao: str | None = None
    preco: float = Field(ge=0)
    preco_anual: float | None = Field(default=None, ge=0)
    ativo: bool = True
    periodo_teste_dias: int = Field(default=14, ge=0, le=90)
    limite_usuarios: int | None = Field(default=None, ge=1)
    limite_clientes: int | None = Field(default=None, ge=1)
    limite_agendamentos_mes: int | None = Field(default=None, ge=1)
    limite_conversas_mes: int | None = Field(default=None, ge=1)
    limite_mensagens_ia_mes: int | None = Field(default=None, ge=0)
    limite_canais: int | None = Field(default=None, ge=1)
    limite_armazenamento_mb: int | None = Field(default=None, ge=1)
    ia_incluida: bool = False
    ia_adicional_disponivel: bool = True
    recursos: dict[str, bool] = Field(default_factory=dict)


class PlanoCreate(PlanoBase):
    codigo: str = Field(min_length=2, max_length=40, pattern=r"^[A-Z0-9_]+$")


class PlanoUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=60)
    descricao: str | None = None
    preco: float | None = Field(default=None, ge=0)
    preco_anual: float | None = Field(default=None, ge=0)
    ativo: bool | None = None
    periodo_teste_dias: int | None = Field(default=None, ge=0, le=90)
    limite_usuarios: int | None = Field(default=None, ge=1)
    limite_clientes: int | None = Field(default=None, ge=1)
    limite_agendamentos_mes: int | None = Field(default=None, ge=1)
    limite_conversas_mes: int | None = Field(default=None, ge=1)
    limite_mensagens_ia_mes: int | None = Field(default=None, ge=0)
    limite_canais: int | None = Field(default=None, ge=1)
    limite_armazenamento_mb: int | None = Field(default=None, ge=1)
    ia_incluida: bool | None = None
    ia_adicional_disponivel: bool | None = None
    recursos: dict[str, bool] | None = None


class PlanoOut(PlanoBase):
    id: int
    codigo: str
    created_at: datetime
    updated_at: datetime


class EmpresaSuperAdminCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    cnpj: str = Field(min_length=11, max_length=18)
    telefone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=150)
    cidade: str | None = Field(default=None, max_length=100)
    estado: str | None = Field(default=None, min_length=2, max_length=2)
    timezone: str = Field(default="America/Sao_Paulo", max_length=50)
    plano_id: int = Field(gt=0)
    periodo_teste_dias: int = Field(default=14, ge=0, le=90)
    admin_nome: str = Field(min_length=2, max_length=150)
    admin_email: str = Field(min_length=3, max_length=150)
    admin_senha: str = Field(min_length=8, max_length=128)


class EmpresaSuperAdminUpdate(BaseModel):
    plano_id: int | None = Field(default=None, gt=0)
    status: StatusPlataforma | None = None
    trial_fim: date | None = None
    recursos_personalizados: dict[str, bool] | None = None
    limites_personalizados: dict[str, int | None] | None = None
    ia_adicional_ativo: bool | None = None
    ia_limite_adicional: int | None = Field(default=None, ge=0)
    observacoes: str | None = None


class EmpresaResumoOut(BaseModel):
    id: int
    nome: str
    cnpj: str
    email: str | None
    cidade: str | None
    estado: str | None
    ativo: bool
    status: StatusPlataforma
    plano_id: int | None
    plano_nome: str | None
    trial_fim: date | None
    usuarios_ativos: int
    clientes: int
    agendamentos_mes: int
    conversas_mes: int
    ia_adicional_ativo: bool
    created_at: datetime


class UsoEmpresaOut(BaseModel):
    usuarios_ativos: int
    clientes: int
    agendamentos_mes: int
    conversas_mes: int
    canais_ativos: int
    mensagens_ia_mes: int
    limites: dict[str, int | None]
    recursos: dict[str, bool]


class EmpresaDetalheOut(BaseModel):
    id: int
    nome: str
    cnpj: str
    telefone: str | None
    email: str | None
    cidade: str | None
    estado: str | None
    timezone: str
    ativo: bool
    status: StatusPlataforma
    plano_id: int | None
    plano_nome: str | None
    trial_fim: date | None
    recursos_personalizados: dict[str, bool]
    limites_personalizados: dict[str, int | None]
    ia_adicional_ativo: bool
    ia_limite_adicional: int
    observacoes: str | None
    uso: UsoEmpresaOut
    created_at: datetime
    updated_at: datetime


class ConfigIASuperAdminUpdate(BaseModel):
    nome_assistente: str = Field(min_length=2, max_length=80)
    mensagem_boas_vindas: str | None = None
    prompt: str | None = None
    temperatura: Decimal = Field(ge=0, le=2, max_digits=3, decimal_places=2)


class ConfigIASuperAdminOut(ORMModel):
    id: int
    empresa_id: int
    nome_assistente: str
    mensagem_boas_vindas: str | None
    prompt: str | None
    temperatura: Decimal


class DashboardSuperAdminOut(BaseModel):
    empresas_total: int
    empresas_ativas: int
    empresas_trial: int
    empresas_suspensas: int
    usuarios_ativos: int
    agendamentos_mes: int
    conversas_mes: int
    planos_ativos: int
    empresas_por_plano: list[dict[str, int | str]]
    alertas: list[dict[str, str]]


class SuperAdminLogOut(ORMModel):
    id: int
    super_admin_id: int | None
    empresa_id: int | None
    acao: str
    entidade: str | None
    entidade_id: int | None
    dados_anteriores: dict | None
    dados_novos: dict | None
    ip: str | None
    created_at: datetime
