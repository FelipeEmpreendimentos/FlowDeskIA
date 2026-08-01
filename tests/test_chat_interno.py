import pytest
from pydantic import ValidationError

from app.main import app
from app.schemas.internal_chat import ChatInternoMensagemCreate


def test_rotas_do_chat_interno_estao_registradas() -> None:
    paths = app.openapi()["paths"]

    assert "/api/v1/chat-interno/mensagens" in paths
    assert "/api/v1/chat-interno/resumo" in paths
    assert "/api/v1/chat-interno/marcar-lido" in paths


def test_mensagem_do_chat_respeita_limite() -> None:
    mensagem = ChatInternoMensagemCreate(conteudo="Bom dia, equipe!")
    assert mensagem.conteudo == "Bom dia, equipe!"

    with pytest.raises(ValidationError):
        ChatInternoMensagemCreate(conteudo="x" * 2001)
