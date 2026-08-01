from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import CargoUsuario


class ChatInternoMensagemCreate(BaseModel):
    conteudo: str = Field(min_length=1, max_length=2000)


class ChatInternoAutorOut(BaseModel):
    id: int
    nome: str
    cargo: CargoUsuario
    foto_perfil: str | None


class ChatInternoMensagemOut(BaseModel):
    id: int
    conteudo: str
    created_at: datetime
    autor: ChatInternoAutorOut


class ChatInternoResumoOut(BaseModel):
    nao_lidas: int
    ultima_mensagem_id: int | None


class ChatInternoLeituraOut(BaseModel):
    ultima_mensagem_id: int
    updated_at: datetime
