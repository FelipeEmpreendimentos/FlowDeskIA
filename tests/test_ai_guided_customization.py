from types import SimpleNamespace

from app.services.ai_guided_customization import (
    _preserve_context_prefix,
    _question_for_state,
    _render_template,
)
from app.services.ai_guided_flow import GuidedAgentResult, QuickReply


def _result(state: str, options: list[QuickReply], interpreted_as: str | None = None) -> GuidedAgentResult:
    return GuidedAgentResult(
        text="Texto original",
        model="flowdesk-guided",
        response_id=None,
        tool_trace=[],
        intent="AGENDAR",
        state=state,
        handoff=False,
        handoff_reason=None,
        customer_id=1,
        customer_complete=True,
        pending_action=None,
        options=options,
        interpreted_as=interpreted_as,
    )


def test_maps_service_state_without_changing_action_id() -> None:
    result = _result(
        "AGENDAR_SERVICO",
        [QuickReply(id="AGENDAR_SERVICO:42", label="Lavagem completa")],
    )

    assert _question_for_state(result) == "servico"
    assert result.options[0].id == "AGENDAR_SERVICO:42"


def test_does_not_replace_no_availability_message_with_hour_question() -> None:
    result = _result(
        "AGENDAR_HORARIO",
        [QuickReply(id="AGENDAR_DATA:2026-08-25", label="25/08")],
    )

    assert _question_for_state(result) is None


def test_renders_dynamic_question_variables() -> None:
    empresa = SimpleNamespace(nome="Lava Car Teste")
    cliente = SimpleNamespace(nome="Felipe Lasta")

    text = _render_template(
        "{{primeiro_nome}}, encontrei horários em {{data}} para {{servico}} na {{empresa}}.",
        empresa=empresa,
        cliente=cliente,
        context={"data": "2026-08-25", "servico_nome": "Lavagem completa"},
    )

    assert text == "Felipe, encontrei horários em 25/08 para Lavagem completa na Lava Car Teste."


def test_preserves_vehicle_recognition_before_custom_date_question() -> None:
    original = "Perfeito, entendi que é um Chevrolet Corsa. Para qual dia você prefere?"

    text = _preserve_context_prefix(
        original,
        "Que dia fica melhor para você?",
        key="data_agendamento",
        interpreted_as="VEICULO_IDENTIFICADO",
    )

    assert text == "Perfeito, entendi que é um Chevrolet Corsa. Que dia fica melhor para você?"


def test_preserves_interpretation_prefix_for_custom_service_question() -> None:
    original = "Entendi que você quer realizar um agendamento.\n\nQual serviço você quer agendar?"

    text = _preserve_context_prefix(
        original,
        "Qual serviço você gostaria de fazer?",
        key="servico",
        interpreted_as="AGENDAR",
    )

    assert text == "Entendi que você quer realizar um agendamento.\n\nQual serviço você gostaria de fazer?"
