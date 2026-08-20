from pydantic import BaseModel, Field

from app.schemas.ai import MenuIAItem


class PerguntasBasicasIA(BaseModel):
    servico: str = Field(min_length=1, max_length=300)
    nome: str = Field(min_length=1, max_length=300)
    email: str = Field(min_length=1, max_length=300)
    veiculo_novo: str = Field(min_length=1, max_length=400)
    veiculo_existente: str = Field(min_length=1, max_length=300)
    data_agendamento: str = Field(min_length=1, max_length=300)
    data_reagendamento: str = Field(min_length=1, max_length=300)
    horario: str = Field(min_length=1, max_length=300)
    consulta_agendamento: str = Field(min_length=1, max_length=300)
    cancelamento: str = Field(min_length=1, max_length=300)
    reagendamento: str = Field(min_length=1, max_length=300)


class AIPersonalizationPut(BaseModel):
    texto_menu_principal: str | None = Field(default=None, max_length=500)
    menu_principal: list[MenuIAItem] = Field(default_factory=list, max_length=6)
    perguntas_basicas: PerguntasBasicasIA


class AIPersonalizationOut(AIPersonalizationPut):
    empresa_id: int
