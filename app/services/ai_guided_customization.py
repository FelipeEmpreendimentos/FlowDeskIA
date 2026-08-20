from __future__ import annotations

from dataclasses import replace
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import DEFAULT_AI_QUESTIONS
from app.models.models import Cliente, Empresa
from app.services.ai_agent import _session, _settings
from app.services.ai_guided_autonomy import run_autonomous_guided_agent
from app.services.ai_guided_flow import GuidedAgentResult


def _render_template(template: str, *, empresa: Empresa, cliente: Cliente, context: dict) -> str:
    data_value = context.get("data")
    data_label = ""
    if data_value:
        try:
            data_label = date.fromisoformat(str(data_value)).strftime("%d/%m")
        except ValueError:
            data_label = str(data_value)

    replacements = {
        "{{primeiro_nome}}": (cliente.nome.split()[0] if cliente.nome else ""),
        "{{nome_cliente}}": cliente.nome or "",
        "{{empresa}}": empresa.nome,
        "{{data}}": data_label,
        "{{servico}}": str(context.get("servico_nome") or ""),
    }
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    return " ".join(rendered.split()).strip()


def _question_for_state(result: GuidedAgentResult) -> str | None:
    option_ids = [option.id for option in result.options]
    if result.state == "AGENDAR_SERVICO" and any(value.startswith("AGENDAR_SERVICO:") for value in option_ids):
        return "servico"
    if result.state == "AGENDAR_CLIENTE_NOME":
        return "nome"
    if result.state == "AGENDAR_CLIENTE_EMAIL":
        return "email"
    if result.state == "AGENDAR_VEICULO_NOVO":
        return "veiculo_novo"
    if result.state == "AGENDAR_VEICULO" and any(value.startswith("AGENDAR_VEICULO:") for value in option_ids):
        return "veiculo_existente"
    if result.state == "AGENDAR_DATA":
        return "data_agendamento"
    if result.state == "REAGENDAR_DATA":
        return "data_reagendamento"
    if result.state in {"AGENDAR_HORARIO", "REAGENDAR_HORARIO"} and any(
        value.startswith(("AGENDAR_HORA:", "REAGENDAR_HORA:")) for value in option_ids
    ):
        return "horario"
    if result.state == "CONSULTAR_AGENDAMENTO" and any(value.startswith("AGENDAMENTO_VER:") for value in option_ids):
        return "consulta_agendamento"
    if result.state == "CANCELAR_ESCOLHER" and any(value.startswith("CANCELAR_ESCOLHER:") for value in option_ids):
        return "cancelamento"
    if result.state == "REAGENDAR_ESCOLHER" and any(value.startswith("REAGENDAR_ESCOLHER:") for value in option_ids):
        return "reagendamento"
    return None


def _preserve_context_prefix(
    original: str,
    customized: str,
    *,
    key: str,
    interpreted_as: str | None,
) -> str:
    if "\n\n" in original:
        first, rest = original.split("\n\n", 1)
        if "entendi que" in first.lower():
            return f"{first}\n\n{customized}"
        if key == "email" and "prazer" in first.lower():
            return f"{first}\n\n{customized}"
        if rest.strip() == DEFAULT_AI_QUESTIONS.get(key, "").strip():
            return f"{first}\n\n{customized}"

    if interpreted_as == "VEICULO_IDENTIFICADO" and key in {"data_agendamento", "data_reagendamento"}:
        default_question = "Para qual dia você prefere?"
        if original.endswith(default_question):
            prefix = original[: -len(default_question)].rstrip()
            return f"{prefix} {customized}".strip()

    return customized


def run_customized_guided_agent(
    db: Session,
    *,
    empresa_id: int,
    cliente_id: int,
    session_id: str,
    transcript: list[tuple[str, str]],
    action_id: str | None = None,
    canal: str = "WHATSAPP_SIMULADO",
) -> GuidedAgentResult:
    result = run_autonomous_guided_agent(
        db,
        empresa_id=empresa_id,
        cliente_id=cliente_id,
        session_id=session_id,
        transcript=transcript,
        action_id=action_id,
        canal=canal,
    )

    key = _question_for_state(result)
    if not key:
        return result

    empresa = db.scalar(select(Empresa).where(Empresa.id == empresa_id))
    cliente = db.scalar(
        select(Cliente).where(
            Cliente.id == cliente_id,
            Cliente.empresa_id == empresa_id,
        )
    )
    if empresa is None or cliente is None:
        return result

    settings = _settings(db, empresa_id)
    questions = settings.perguntas_basicas if isinstance(settings.perguntas_basicas, dict) else {}
    template = str(questions.get(key) or DEFAULT_AI_QUESTIONS[key]).strip()
    session = _session(
        db,
        empresa_id=empresa_id,
        external_id=session_id,
        cliente_id=cliente_id,
        canal=canal,
    )
    customized = _render_template(
        template,
        empresa=empresa,
        cliente=cliente,
        context=dict(session.flow_context or {}),
    )
    if not customized:
        return result
    return replace(
        result,
        text=_preserve_context_prefix(
            result.text,
            customized,
            key=key,
            interpreted_as=result.interpreted_as,
        ),
    )
