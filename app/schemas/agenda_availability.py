from datetime import time

from pydantic import BaseModel


class SlotDisponivelDetalhado(BaseModel):
    hora_inicio: time
    hora_fim: time
    funcionario_id: int
    funcionario_nome: str
