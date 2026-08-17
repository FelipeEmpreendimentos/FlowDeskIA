from types import SimpleNamespace

from app.services.ai_agent import (
    _greeting,
    _is_explicit_confirmation,
    _is_greeting_only,
)


def test_greeting_detector_does_not_interrogate_simple_hello() -> None:
    assert _is_greeting_only("Oi") is True
    assert _is_greeting_only("Olá, tudo bem?") is True
    assert _is_greeting_only("Oi, quero agendar uma lavagem") is False


def test_confirmation_requires_clear_positive_message() -> None:
    assert _is_explicit_confirmation("Sim, pode confirmar.") is True
    assert _is_explicit_confirmation("Pode agendar") is True
    assert _is_explicit_confirmation("Fechado") is True
    assert _is_explicit_confirmation("Não, espera") is False
    assert _is_explicit_confirmation("Talvez") is False


def test_known_customer_greeting_renders_company_variables() -> None:
    empresa = SimpleNamespace(nome="Lava Car Teste")
    config = SimpleNamespace(nome_assistente="Lia", mensagem_boas_vindas=None)
    settings = SimpleNamespace(
        saudacao_cliente_conhecido=(
            "Olá, {{primeiro_nome}}! Sou a {{nome_assistente}} da {{empresa}}. Como posso ajudar?"
        ),
        saudacao_cliente_novo=None,
    )
    cliente = SimpleNamespace(nome="Carlos da Silva")

    result = _greeting(
        empresa,
        config,
        settings,
        cliente,
        True,
    )

    assert result == "Olá, Carlos! Sou a Lia da Lava Car Teste. Como posso ajudar?"


def test_new_customer_greeting_does_not_expose_placeholder_name() -> None:
    empresa = SimpleNamespace(nome="Lava Car Teste")
    config = SimpleNamespace(nome_assistente="Lia", mensagem_boas_vindas=None)
    settings = SimpleNamespace(
        saudacao_cliente_conhecido=None,
        saudacao_cliente_novo="Olá! Sou a {{nome_assistente}} da {{empresa}}. Como posso ajudar?",
    )
    cliente = SimpleNamespace(nome="Contato WhatsApp 1234")

    result = _greeting(
        empresa,
        config,
        settings,
        cliente,
        False,
    )

    assert "Contato WhatsApp" not in result
    assert result == "Olá! Sou a Lia da Lava Car Teste. Como posso ajudar?"
