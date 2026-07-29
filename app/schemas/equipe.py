from datetime import time

from pydantic import BaseModel, Field


class JornadaSemanalDia(BaseModel):
    dia_semana: int = Field(ge=0, le=6)
    hora_inicio: time
    hora_fim: time
    ativo: bool = True


class JornadaSemanalUpdate(BaseModel):
    dias: list[JornadaSemanalDia] = Field(min_length=1, max_length=7)
