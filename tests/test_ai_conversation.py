from datetime import time
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.models.enums import RemetenteMensagem
from app.services import ai_conversation
from app.services.ai_conversation import (
    AIContext,
    AIConversationStateError,
    AIProviderResponse,
)


def _conversation(*, ia_ativa: bool = True):
    return SimpleNamespace(
        id=41,
        empresa_id=3,
        cliente_id=7,
        ia_ativa=ia_ativa,
        ultima_mensagem_id=None,
        ultima_interacao=None,
    )


def test_ia_nao_responde_quando_esta_pausada() -> None:
    db = Mock()

    with pytest.raises(AIConversationStateError) as exc_info:
        ai_conversation.generate_ai_reply(db, _conversation(ia_ativa=False))

    assert "pausada" in str(exc_info.value).lower()
    db.add.assert_not_called()


def test_ia_so_responde_quando_ultima_mensagem_e_do_cliente() -> None:
    db = Mock()
    latest = SimpleNamespace(remetente=RemetenteMensagem.IA)

    with (
        patch.object(ai_conversation, "_latest_message", return_value=latest),
        patch.object(ai_conversation, "request_openai") as provider,
    ):
        with pytest.raises(AIConversationStateError) as exc_info:
            ai_conversation.generate_ai_reply(db, _conversation())

    assert "última mensagem" in str(exc_info.value).lower()
    provider.assert_not_called()
    db.add.assert_not_called()


def test_ia_persiste_resposta_e_atualiza_conversa() -> None:
    db = Mock()
    conversa = _conversation()
    latest = SimpleNamespace(remetente=RemetenteMensagem.CLIENTE)
    context = AIContext(
        instructions="Instruções",
        input_text="Contexto",
        model="gpt-5-mini",
    )
    provider_response = AIProviderResponse(
        text="Claro! Posso te ajudar com isso.",
        response_id="resp_123",
        model="gpt-5-mini",
    )

    def assign_message_id() -> None:
        message = db.add.call_args_list[0].args[0]
        message.id = 88

    db.flush.side_effect = assign_message_id

    with (
        patch.object(ai_conversation, "_latest_message", return_value=latest),
        patch.object(ai_conversation, "build_ai_context", return_value=context),
        patch.object(
            ai_conversation,
            "request_openai",
            return_value=provider_response,
        ),
    ):
        message = ai_conversation.generate_ai_reply(db, conversa)

    assert message.id == 88
    assert message.remetente == RemetenteMensagem.IA
    assert message.conteudo == provider_response.text
    assert conversa.ultima_mensagem_id == 88
    assert conversa.ultima_interacao is not None
    assert db.add.call_count == 2

    log = db.add.call_args_list[1].args[0]
    assert log.detalhes["conversa_id"] == conversa.id
    assert log.detalhes["modelo"] == "gpt-5-mini"
    assert log.detalhes["openai_response_id"] == "resp_123"


def test_contexto_usa_dados_reais_da_empresa_cliente_e_historico() -> None:
    db = Mock()
    conversa = _conversation()

    empresa = SimpleNamespace(
        id=3,
        nome="Estética Exemplo",
        cidade="Pato Branco",
        estado="PR",
        timezone="America/Sao_Paulo",
        horario_abertura=time(8, 0),
        horario_fechamento=time(18, 0),
    )
    cliente = SimpleNamespace(
        nome="Felipe",
        observacoes="Prefere lavagem sem perfume.",
    )
    config = SimpleNamespace(
        nome_assistente="Lia",
        prompt="Seja objetiva e cordial.",
    )
    servico = SimpleNamespace(
        nome="Lavagem completa",
        preco=Decimal("120.00"),
        duracao_minutos=90,
        descricao="Lavagem interna e externa.",
    )
    veiculo = SimpleNamespace(
        marca="Honda",
        modelo="Civic",
        ano=2024,
        placa="ABC1D23",
        apelido=None,
    )
    memoria = SimpleNamespace(
        categoria="preferência",
        informacao="Gosta de atendimento no período da manhã.",
    )
    mensagem = SimpleNamespace(
        remetente=RemetenteMensagem.CLIENTE,
        conteudo="Quanto custa a lavagem completa?",
    )

    db.scalar.side_effect = [empresa, cliente, config]
    db.scalars.side_effect = [
        [servico],
        [veiculo],
        [memoria],
        [mensagem],
    ]

    context = ai_conversation.build_ai_context(db, conversa)

    assert "Estética Exemplo" in context.input_text
    assert "Lavagem completa: R$ 120,00" in context.input_text
    assert "Honda Civic" in context.input_text
    assert "Felipe" in context.input_text
    assert "Gosta de atendimento" in context.input_text
    assert "Quanto custa a lavagem completa?" in context.input_text
    assert "Seja objetiva e cordial." in context.instructions
    assert "NÃO possui ferramenta" in context.instructions
