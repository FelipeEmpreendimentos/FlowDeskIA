import pytest
from pydantic import ValidationError

from app.main import app
from app.schemas.internal_chat import (
    ChatInternoGrupoCreate,
    ChatInternoMensagemCreate,
)


def test_rotas_do_chat_interno_estao_registradas() -> None:
    paths = app.openapi()["paths"]

    assert "/api/v1/chat-interno/usuarios" in paths
    assert "/api/v1/chat-interno/canais" in paths
    assert "/api/v1/chat-interno/diretos" in paths
    assert "/api/v1/chat-interno/grupos" in paths
    assert "/api/v1/chat-interno/resumo" in paths
    assert "/api/v1/chat-interno/canais/{canal_id}/mensagens" in paths
    assert "/api/v1/chat-interno/canais/{canal_id}/marcar-lido" in paths


def test_mensagem_do_chat_respeita_limite() -> None:
    mensagem = ChatInternoMensagemCreate(conteudo="Bom dia, equipe!")
    assert mensagem.conteudo == "Bom dia, equipe!"

    with pytest.raises(ValidationError):
        ChatInternoMensagemCreate(conteudo="x" * 2001)


def test_grupo_exige_nome_e_participante() -> None:
    grupo = ChatInternoGrupoCreate(nome="Equipe da manhã", usuario_ids=[2, 3])
    assert grupo.nome == "Equipe da manhã"
    assert grupo.usuario_ids == [2, 3]

    with pytest.raises(ValidationError):
        ChatInternoGrupoCreate(nome="A", usuario_ids=[])
