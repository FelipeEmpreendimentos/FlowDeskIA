from pydantic import BaseModel, Field

from app.models.enums import CargoUsuario
from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    empresa_id: int = Field(gt=0)
    email: str = Field(min_length=3, max_length=150)
    senha: str = Field(min_length=6, max_length=128)
    manter_conectado: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AlterarSenhaRequest(BaseModel):
    senha_atual: str = Field(min_length=6, max_length=128)
    nova_senha: str = Field(min_length=8, max_length=128)


class UsuarioLogado(ORMModel):
    id: int
    empresa_id: int
    nome: str
    email: str
    cargo: CargoUsuario
    ativo: bool


class RecuperarSenhaRequest(BaseModel):
    empresa_id: int = Field(gt=0)
    email: str = Field(min_length=3, max_length=150)


class RecuperarSenhaResponse(BaseModel):
    mensagem: str


class RedefinirSenhaRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    nova_senha: str = Field(min_length=8, max_length=128)
