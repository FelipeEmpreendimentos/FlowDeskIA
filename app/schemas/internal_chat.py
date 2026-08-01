from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import CargoUsuario


TipoCanalChatInterno = Literal["GERAL", "DIRETO", "GRUPO"]


class ChatInternoMensagemCreate(BaseModel):
    conteudo: str = Field(min_length=1, max_length=2000)


class ChatInternoDiretoCreate(BaseModel):
    usuario_id: int = Field(gt=0)


class ChatInternoGrupoCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=80)
    usuario_ids: list[int] = Field(min_length=1, max_length=50)


class ChatInternoAutorOut(BaseModel):
    id: int
    nome: str
    cargo: CargoUsuario
    foto_perfil: str | None
    ativo: bool = True


class ChatInternoMensagemOut(BaseModel):
    id: int
    canal_id: int
    conteudo: str
    created_at: datetime
    autor: ChatInternoAutorOut


class ChatInternoCanalOut(BaseModel):
    id: int
    tipo: TipoCanalChatInterno
    nome: str
    created_at: datetime
    membros: list[ChatInternoAutorOut]
    ultima_mensagem: ChatInternoMensagemOut | None
    nao_lidas: int


class ChatInternoResumoOut(BaseModel):
    nao_lidas: int
    ultima_mensagem_id: int | None


class ChatInternoLeituraOut(BaseModel):
    canal_id: int
    ultima_mensagem_id: int
    updated_at: datetime
