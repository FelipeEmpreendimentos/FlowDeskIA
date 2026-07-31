from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class OnboardingEtapaOut(BaseModel):
    chave: str
    titulo: str
    descricao: str
    concluida: bool
    link: str


class OnboardingOut(BaseModel):
    oculto: bool
    concluido: bool
    percentual: int
    concluidas: int
    total: int
    etapas: list[OnboardingEtapaOut]


class OnboardingOcultarInput(BaseModel):
    oculto: bool


class PreferenciaNotificacaoOut(ORMModel):
    id: int
    empresa_id: int
    usuario_id: int
    agendamentos: bool
    financeiro: bool
    conversas: bool
    avaliacoes: bool
    integracoes: bool
    planos_limites: bool
    sistema: bool
    updated_at: datetime


class PreferenciaNotificacaoUpdate(BaseModel):
    agendamentos: bool
    financeiro: bool
    conversas: bool
    avaliacoes: bool
    integracoes: bool
    planos_limites: bool
    sistema: bool
