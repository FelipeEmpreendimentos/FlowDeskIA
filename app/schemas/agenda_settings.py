from typing import Literal

from pydantic import BaseModel

from app.schemas.common import ORMModel


IntervaloAgenda = Literal[15, 30, 60]


class ConfiguracaoAgendaOut(ORMModel):
    empresa_id: int
    intervalo_minutos: int


class ConfiguracaoAgendaUpdate(BaseModel):
    intervalo_minutos: IntervaloAgenda
