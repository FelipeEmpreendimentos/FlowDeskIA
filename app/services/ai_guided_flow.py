from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import AIAttendanceSession, AICompanySettings, DEFAULT_AI_MENU
from app.models.enums import StatusAgendamento
from app.models.models import Agendamento, Cliente, ConfigIA, Empresa, Servico, Veiculo
from app.services.ai_agent import (
    AIAgentResult,
    AgentToolTrace,
    _Executor,
    _active_services,
    _contact_metadata,
    _customer_complete,
    _greeting,
    _local_now,
    _money,
    _session,
    _settings,
    _transfer_message,
    _vehicle_label,
    _vehicles,
    run_operational_agent,
)

MAX_QUICK_OPTIONS = 8


@dataclass(frozen=True)
class QuickReply:
    id: str
    label: str
    kind: str = "default"


@dataclass(frozen=True)
class GuidedAgentResult:
    text: str
    model: str
    response_id: str | None
    tool_trace: list[AgentToolTrace]
    intent: str | None
    state: str
    handoff: bool
    handoff_reason: str | None
    customer_id: int | None
    customer_complete: bool
    pending_action: dict[str, Any] | None
    options: list[QuickReply]
    interpreted_as: str | None = None


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).strip()


def _clean_text(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9@./:+ -]+", " ", _normalize(value)).split())


def _is_menu_request(value: str) -> bool:
    text = _clean_text(value)
    return text in {
        "menu",
        "inicio",
        "voltar",
        "voltar ao inicio",
        "comecar de novo",
        "recomecar",
        "outra coisa",
    }


def _greeting_phrase(value: str) -> str | None:
    text = _clean_text(value)
    if text.startswith("bom dia"):
        return "Bom dia"
    if text.startswith("boa tarde"):
        return "Boa tarde"
    if text.startswith("boa noite"):
        return "Boa noite"
    if text in {"oi", "ola", "opa", "e ai", "eai", "oi tudo bem", "ola tudo bem"}:
        return "Olá"
    return None


def _apply_user_greeting(base: str, user_text: str) -> str:
    greeting = _greeting_phrase(user_text)
    if not greeting:
        return base
    pattern = re.compile(r"^(olá|ola|oi|bom dia|boa tarde|boa noite)\b", re.IGNORECASE)
    if pattern.search(base):
        return pattern.sub(greeting, base, count=1)
    return f"{greeting}! {base}".strip()


def _infer_standard_intent(value: str) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    if _greeting_phrase(value):
        return "SAUDACAO"
    if any(token in text for token in ("atendente", "humano", "pessoa da equipe", "falar com alguem", "gerente")):
        return "HUMANO"
    if any(token in text for token in ("reagendar", "remarcar", "trocar horario", "mudar horario", "mudar meu horario")):
        return "REAGENDAR"
    if any(token in text for token in ("cancelar", "desmarcar", "cancela meu", "nao vou conseguir ir")):
        return "CANCELAR"
    if any(token in text for token in ("consultar agendamento", "meu agendamento", "meus agendamentos", "horario marcado", "que horas marquei", "quando marquei")):
        return "CONSULTAR_AGENDAMENTO"
    if any(token in text for token in ("preco", "preços", "quanto custa", "valor", "servicos", "serviço", "o que voces fazem", "o que fazem")):
        return "SERVICOS_PRECOS"
    if any(token in text for token in ("agendar", "marcar um horario", "marcar horario", "quero horario", "reservar horario")):
        return "AGENDAR"
    return None


def _menu_items(settings: AICompanySettings) -> list[dict[str, Any]]:
    raw = settings.menu_principal or [dict(item) for item in DEFAULT_AI_MENU]
    allowed: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict) or not item.get("ativo", True):
            continue
        action = str(item.get("acao") or "")
        if action == "AGENDAR" and not settings.pode_agendar:
            continue
        if action == "REAGENDAR" and not settings.pode_reagendar:
            continue
        if action == "CANCELAR" and not settings.pode_cancelar:
            continue
        allowed.append(item)
    allowed.sort(key=lambda item: (int(item.get("ordem") or 999), str(item.get("rotulo") or "")))
    return allowed[:MAX_QUICK_OPTIONS]


def _menu_options(settings: AICompanySettings) -> list[QuickReply]:
    return [
        QuickReply(
            id=f"MENU:{item['acao']}",
            label=str(item.get("rotulo") or item["acao"]).strip()[:40],
            kind="human" if item["acao"] == "HUMANO" else "default",
        )
        for item in _menu_items(settings)
    ]


def _menu_prompt(settings: AICompanySettings) -> str:
    return (settings.texto_menu_principal or "Como posso ajudar hoje?").strip()


def _known_customer(db: Session, cliente: Cliente, settings: AICompanySettings) -> tuple[bool, bool]:
    metadata = _contact_metadata(db, cliente)
    complete = _customer_complete(cliente, metadata, settings)
    return metadata is None or complete, complete


def _save_flow(
    db: Session,
    session: AIAttendanceSession,
    *,
    state: str,
    intent: str | None = None,
    context: dict[str, Any] | None = None,
    clear_pending: bool = False,
) -> None:
    session.estado = state
    session.last_intent = intent or session.last_intent
    session.flow_context = context
    if clear_pending:
        session.pending_action = None
    session.updated_at = datetime.now(timezone.utc)
    db.commit()


def _base_result(
    db: Session,
    *,
    cliente: Cliente,
    settings: AICompanySettings,
    session: AIAttendanceSession,
    text: str,
    options: list[QuickReply],
    intent: str | None = None,
    model: str = "flowdesk-guided",
    trace: list[AgentToolTrace] | None = None,
    interpreted_as: str | None = None,
) -> GuidedAgentResult:
    _, complete = _known_customer(db, cliente, settings)
    return GuidedAgentResult(
        text=text,
        model=model,
        response_id=None,
        tool_trace=trace or [],
        intent=intent or session.last_intent,
        state=session.estado,
        handoff=session.estado == "HUMANO",
        handoff_reason=session.handoff_motivo,
        customer_id=cliente.id,
        customer_complete=complete,
        pending_action=session.pending_action,
        options=options,
        interpreted_as=interpreted_as,
    )


def _from_agent(result: AIAgentResult, options: list[QuickReply], interpreted_as: str | None = None) -> GuidedAgentResult:
    return GuidedAgentResult(
        text=result.text,
        model=result.model,
        response_id=result.response_id,
        tool_trace=result.tool_trace,
        intent=result.intent,
        state=result.state,
        handoff=result.handoff,
        handoff_reason=result.handoff_reason,
        customer_id=result.customer_id,
        customer_complete=result.customer_complete,
        pending_action=result.pending_action,
        options=options,
        interpreted_as=interpreted_as,
    )


def _trace_tool(
    executor: _Executor,
    trace: list[AgentToolTrace],
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    result = executor.execute(name, arguments)
    trace.append(AgentToolTrace(name=name, arguments=arguments, result=result))
    return result


def _executor(
    db: Session,
    empresa: Empresa,
    cliente: Cliente,
    settings: AICompanySettings,
    session: AIAttendanceSession,
    latest_user_text: str,
) -> _Executor:
    return _Executor(
        db=db,
        empresa=empresa,
        cliente=cliente,
        company_settings=settings,
        session=session,
        latest_user_text=latest_user_text,
    )


def _interpret_prefix(settings: AICompanySettings, label: str) -> str:
    return f"Entendi que você quer {label}.\n\n" if settings.mostrar_interpretacao else ""


def _service_options(services: list[Servico], prefix: str) -> list[QuickReply]:
    return [
        QuickReply(id=f"{prefix}:{service.id}", label=service.nome[:40])
        for service in services[:MAX_QUICK_OPTIONS]
    ]


def _vehicle_options(vehicles: list[Veiculo], prefix: str) -> list[QuickReply]:
    return [
        QuickReply(id=f"{prefix}:{vehicle.id}", label=_vehicle_label(vehicle)[:40])
        for vehicle in vehicles[: MAX_QUICK_OPTIONS - 1]
    ] + [QuickReply(id="VEICULO:NOVO", label="Outro veículo")]


def _date_options(prefix: str, empresa: Empresa) -> list[QuickReply]:
    today = _local_now(empresa).date()
    return [
        QuickReply(id=f"{prefix}:{today.isoformat()}", label="Hoje"),
        QuickReply(id=f"{prefix}:{(today + timedelta(days=1)).isoformat()}", label="Amanhã"),
        QuickReply(id=f"{prefix}:{(today + timedelta(days=2)).isoformat()}", label="Depois de amanhã"),
        QuickReply(id=f"{prefix}:DIGITAR", label="Outra data"),
        QuickReply(id="MENU:INICIO", label="Voltar ao início", kind="secondary"),
    ]


def _parse_user_date(value: str, today: date) -> date | None:
    text = _clean_text(value)
    if "depois de amanha" in text:
        return today + timedelta(days=2)
    if "amanha" in text:
        return today + timedelta(days=1)
    if text == "hoje" or " hoje" in f" {text}":
        return today

    iso_match = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", text)
    if iso_match:
        try:
            return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
        except ValueError:
            return None

    br_match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", text)
    if br_match:
        day = int(br_match.group(1))
        month = int(br_match.group(2))
        year_raw = br_match.group(3)
        year = today.year if not year_raw else int(year_raw)
        if year < 100:
            year += 2000
        try:
            candidate = date(year, month, day)
            if not year_raw and candidate < today:
                candidate = date(year + 1, month, day)
            return candidate
        except ValueError:
            return None

    weekday_map = {
        "segunda": 0,
        "terca": 1,
        "quarta": 2,
        "quinta": 3,
        "sexta": 4,
        "sabado": 5,
        "domingo": 6,
    }
    for name, target in weekday_map.items():
        if name in text:
            delta = (target - today.weekday()) % 7
            if delta == 0 and "proxima" in text:
                delta = 7
            return today + timedelta(days=delta)
    return None


def _parse_user_time(value: str) -> str | None:
    text = _clean_text(value)
    match = re.search(r"\b([01]?\d|2[0-3])[:h]([0-5]\d)\b", text)
    if match:
        return f"{int(match.group(1)):02d}:{int(match.group(2)):02d}"
    match = re.search(r"\b([01]?\d|2[0-3])h\b", text)
    if match:
        return f"{int(match.group(1)):02d}:00"
    match = re.fullmatch(r"([01]?\d|2[0-3])", text)
    if match:
        return f"{int(match.group(1)):02d}:00"
    return None


def _active_appointments(db: Session, empresa_id: int, cliente_id: int) -> list[Agendamento]:
    today = datetime.now(timezone.utc).date()
    return list(
        db.scalars(
            select(Agendamento)
            .where(
                Agendamento.empresa_id == empresa_id,
                Agendamento.cliente_id == cliente_id,
                Agendamento.data >= today,
                Agendamento.status.in_([
                    StatusAgendamento.PENDENTE,
                    StatusAgendamento.CONFIRMADO,
                ]),
            )
            .order_by(Agendamento.data, Agendamento.hora_inicio)
            .limit(MAX_QUICK_OPTIONS)
        )
    )


def _appointment_label(db: Session, item: Agendamento) -> str:
    service = db.scalar(select(Servico).where(Servico.id == item.servico_id))
    name = service.nome if service else "Serviço"
    return f"{name} · {item.data.strftime('%d/%m')} {item.hora_inicio.strftime('%H:%M')}"[:40]


def _menu(
    db: Session,
    empresa: Empresa,
    cliente: Cliente,
    base_config: ConfigIA | None,
    settings: AICompanySettings,
    session: AIAttendanceSession,
    user_text: str,
    *,
    interpreted_as: str | None = None,
) -> GuidedAgentResult:
    known, _ = _known_customer(db, cliente, settings)
    greeting = _apply_user_greeting(
        _greeting(empresa, base_config, settings, cliente, known),
        user_text,
    )
    text = greeting
    prompt = _menu_prompt(settings)
    if prompt and prompt.lower() not in greeting.lower():
        text = f"{greeting}\n\n{prompt}"
    _save_flow(
        db,
        session,
        state="MENU",
        intent="SAUDACAO" if _greeting_phrase(user_text) else "MENU",
        context=None,
        clear_pending=True,
    )
    return _base_result(
        db,
        cliente=cliente,
        settings=settings,
        session=session,
        text=text,
        options=_menu_options(settings),
        intent=session.last_intent,
        interpreted_as=interpreted_as,
    )


def _start_services(
    db: Session,
    empresa: Empresa,
    cliente: Cliente,
    settings: AICompanySettings,
    session: AIAttendanceSession,
    *,
    interpreted: bool,
) -> GuidedAgentResult:
    services = _active_services(db, empresa.id)
    _save_flow(db, session, state="SERVICOS", intent="SERVICOS_PRECOS", context=None)
    prefix = _interpret_prefix(settings, "consultar serviços e preços") if interpreted else ""
    if not services:
        return _base_result(
            db,
            cliente=cliente,
            settings=settings,
            session=session,
            text=prefix + "No momento não encontrei serviços ativos cadastrados.",
            options=[QuickReply(id="MENU:INICIO", label="Voltar ao início")],
            interpreted_as="SERVICOS_PRECOS" if interpreted else None,
        )
    return _base_result(
        db,
        cliente=cliente,
        settings=settings,
        session=session,
        text=prefix + "Escolha um serviço para ver os detalhes:",
        options=_service_options(services, "SERVICO_INFO") + [QuickReply(id="MENU:INICIO", label="Voltar")],
        interpreted_as="SERVICOS_PRECOS" if interpreted else None,
    )


def _start_agendar(
    db: Session,
    empresa: Empresa,
    cliente: Cliente,
    settings: AICompanySettings,
    session: AIAttendanceSession,
    *,
    interpreted: bool,
) -> GuidedAgentResult:
    if not settings.pode_agendar:
        return _base_result(
            db,
            cliente=cliente,
            settings=settings,
            session=session,
            text="O agendamento automático não está disponível neste atendimento.",
            options=_menu_options(settings),
            intent="AGENDAR",
        )
    services = _active_services(db, empresa.id)
    _save_flow(db, session, state="AGENDAR_SERVICO", intent="AGENDAR", context={"fluxo": "AGENDAR"}, clear_pending=True)
    prefix = _interpret_prefix(settings, "realizar um agendamento") if interpreted else ""
    if not services:
        return _base_result(
            db,
            cliente=cliente,
            settings=settings,
            session=session,
            text=prefix + "Não encontrei serviços ativos para agendar agora.",
            options=[QuickReply(id="MENU:HUMANO", label="Falar com atendente"), QuickReply(id="MENU:INICIO", label="Voltar")],
            interpreted_as="AGENDAR" if interpreted else None,
        )
    return _base_result(
        db,
        cliente=cliente,
        settings=settings,
        session=session,
        text=prefix + "Qual serviço você quer agendar?",
        options=_service_options(services, "AGENDAR_SERVICO") + [QuickReply(id="MENU:INICIO", label="Voltar")],
        interpreted_as="AGENDAR" if interpreted else None,
    )


def _after_service_selected(
    db: Session,
    empresa: Empresa,
    cliente: Cliente,
    settings: AICompanySettings,
    session: AIAttendanceSession,
    service_id: int,
) -> GuidedAgentResult:
    service = db.scalar(
        select(Servico).where(
            Servico.id == service_id,
            Servico.empresa_id == empresa.id,
            Servico.ativo.is_(True),
        )
    )
    if service is None:
        return _start_agendar(db, empresa, cliente, settings, session, interpreted=False)

    context = {"fluxo": "AGENDAR", "servico_id": service.id, "servico_nome": service.nome}
    required = settings.campos_cliente_obrigatorios or []
    if "nome" in required and (not cliente.nome or cliente.nome.startswith("Contato WhatsApp")):
        _save_flow(db, session, state="AGENDAR_CLIENTE_NOME", intent="AGENDAR", context=context)
        return _base_result(
            db,
            cliente=cliente,
            settings=settings,
            session=session,
            text="Antes de continuar, qual é o seu nome?",
            options=[QuickReply(id="MENU:INICIO", label="Voltar ao início")],
        )
    if "email" in required and not cliente.email:
        _save_flow(db, session, state="AGENDAR_CLIENTE_EMAIL", intent="AGENDAR", context=context)
        return _base_result(
            db,
            cliente=cliente,
            settings=settings,
            session=session,
            text="Qual é o seu e-mail?",
            options=[QuickReply(id="MENU:INICIO", label="Voltar ao início")],
        )
    return _choose_vehicle(db, empresa, cliente, settings, session, context)


def _choose_vehicle(
    db: Session,
    empresa: Empresa,
    cliente: Cliente,
    settings: AICompanySettings,
    session: AIAttendanceSession,
    context: dict[str, Any],
) -> GuidedAgentResult:
    vehicles = _vehicles(db, cliente.id)
    if not settings.campos_veiculo_obrigatorios:
        context = {**context, "veiculo_id": None}
        return _ask_date(db, empresa, cliente, settings, session, context, "AGENDAR")
    if len(vehicles) == 1:
        context = {**context, "veiculo_id": vehicles[0].id}
        return _ask_date(db, empresa, cliente, settings, session, context, "AGENDAR")
    if not vehicles:
        _save_flow(db, session, state="AGENDAR_VEICULO_NOVO", intent="AGENDAR", context=context)
        return _base_result(
            db,
            cliente=cliente,
            settings=settings,
            session=session,
            text="Qual veículo será atendido? Você pode escrever, por exemplo: “Civic sedan 2020 preto”.",
            options=[QuickReply(id="MENU:INICIO", label="Voltar ao início")],
        )
    _save_flow(db, session, state="AGENDAR_VEICULO", intent="AGENDAR", context=context)
    return _base_result(
        db,
        cliente=cliente,
        settings=settings,
        session=session,
        text="Qual veículo você quer usar neste agendamento?",
        options=_vehicle_options(vehicles, "AGENDAR_VEICULO") + [QuickReply(id="MENU:INICIO", label="Voltar")],
    )


def _ask_date(
    db: Session,
    empresa: Empresa,
    cliente: Cliente,
    settings: AICompanySettings,
    session: AIAttendanceSession,
    context: dict[str, Any],
    flow: str,
) -> GuidedAgentResult:
    state = "AGENDAR_DATA" if flow == "AGENDAR" else "REAGENDAR_DATA"
    prefix = "AGENDAR_DATA" if flow == "AGENDAR" else "REAGENDAR_DATA"
    _save_flow(db, session, state=state, intent=flow, context=context)
    return _base_result(
        db,
        cliente=cliente,
        settings=settings,
        session=session,
        text="Para qual dia você prefere?",
        options=_date_options(prefix, empresa),
    )


def _availability_for_date(
    db: Session,
    empresa: Empresa,
    cliente: Cliente,
    settings: AICompanySettings,
    session: AIAttendanceSession,
    target_date: date,
    *,
    flow: str,
) -> GuidedAgentResult:
    context = dict(session.flow_context or {})
    service_id = context.get("servico_id")
    if not service_id:
        return _start_agendar(db, empresa, cliente, settings, session, interpreted=False) if flow == "AGENDAR" else _start_reagendar(db, empresa, cliente, settings, session, interpreted=False)

    executor = _executor(db, empresa, cliente, settings, session, "consultar horários")
    trace: list[AgentToolTrace] = []
    start_filter = None
    if target_date == _local_now(empresa).date():
        start_filter = _local_now(empresa).strftime("%H:%M")
    result = _trace_tool(
        executor,
        trace,
        "consultar_disponibilidade",
        {
            "servico_id": int(service_id),
            "data": target_date.isoformat(),
            "hora_inicio": start_filter,
            "hora_fim": None,
        },
    )
    if not result.get("ok"):
        return _base_result(
            db,
            cliente=cliente,
            settings=settings,
            session=session,
            text=str(result.get("erro") or "Não consegui consultar a agenda agora."),
            options=[QuickReply(id="MENU:HUMANO", label="Falar com atendente"), QuickReply(id="MENU:INICIO", label="Voltar")],
            trace=trace,
        )

    times = [str(item) for item in result.get("horarios", [])]
    context["data"] = target_date.isoformat()
    context["horarios_oferecidos"] = times
    state = "AGENDAR_HORARIO" if flow == "AGENDAR" else "REAGENDAR_HORARIO"
    action_prefix = "AGENDAR_HORA" if flow == "AGENDAR" else "REAGENDAR_HORA"
    _save_flow(db, session, state=state, intent=flow, context=context)

    if not times:
        text = settings.mensagem_indisponibilidade or "Não encontrei horários disponíveis nesse dia. Quer tentar outra data?"
        return _base_result(
            db,
            cliente=cliente,
            settings=settings,
            session=session,
            text=text,
            options=_date_options("AGENDAR_DATA" if flow == "AGENDAR" else "REAGENDAR_DATA", empresa),
            trace=trace,
        )

    return _base_result(
        db,
        cliente=cliente,
        settings=settings,
        session=session,
        text=f"Encontrei estes horários para {target_date.strftime('%d/%m')}. Qual prefere?",
        options=[QuickReply(id=f"{action_prefix}:{hour}", label=hour) for hour in times[:6]]
        + [QuickReply(id="MENU:INICIO", label="Voltar ao início", kind="secondary")],
        trace=trace,
    )


def _start_consult(
    db: Session,
    empresa: Empresa,
    cliente: Cliente,
    settings: AICompanySettings,
    session: AIAttendanceSession,
    *,
    interpreted: bool,
) -> GuidedAgentResult:
    items = _active_appointments(db, empresa.id, cliente.id)
    _save_flow(db, session, state="CONSULTAR_AGENDAMENTO", intent="CONSULTAR_AGENDAMENTO", context=None)
    prefix = _interpret_prefix(settings, "consultar seus agendamentos") if interpreted else ""
    if not items:
        return _base_result(
            db,
            cliente=cliente,
            settings=settings,
            session=session,
            text=prefix + "Não encontrei agendamentos futuros ativos para você.",
            options=[QuickReply(id="MENU:AGENDAR", label="Fazer um agendamento"), QuickReply(id="MENU:INICIO", label="Voltar")],
            interpreted_as="CONSULTAR_AGENDAMENTO" if interpreted else None,
        )
    return _base_result(
        db,
        cliente=cliente,
        settings=settings,
        session=session,
        text=prefix + "Encontrei estes agendamentos. Qual você quer consultar?",
        options=[QuickReply(id=f"AGENDAMENTO_VER:{item.id}", label=_appointment_label(db, item)) for item in items]
        + [QuickReply(id="MENU:INICIO", label="Voltar")],
        interpreted_as="CONSULTAR_AGENDAMENTO" if interpreted else None,
    )


def _start_cancel(
    db: Session,
    empresa: Empresa,
    cliente: Cliente,
    settings: AICompanySettings,
    session: AIAttendanceSession,
    *,
    interpreted: bool,
) -> GuidedAgentResult:
    if not settings.pode_cancelar:
        return _base_result(db, cliente=cliente, settings=settings, session=session, text="O cancelamento automático está desativado.", options=_menu_options(settings), intent="CANCELAR")
    items = _active_appointments(db, empresa.id, cliente.id)
    _save_flow(db, session, state="CANCELAR_ESCOLHER", intent="CANCELAR", context={"fluxo": "CANCELAR"}, clear_pending=True)
    prefix = _interpret_prefix(settings, "cancelar um agendamento") if interpreted else ""
    if not items:
        return _base_result(db, cliente=cliente, settings=settings, session=session, text=prefix + "Não encontrei agendamentos ativos que possam ser cancelados.", options=_menu_options(settings), interpreted_as="CANCELAR" if interpreted else None)
    return _base_result(
        db,
        cliente=cliente,
        settings=settings,
        session=session,
        text=prefix + "Qual agendamento você quer cancelar?",
        options=[QuickReply(id=f"CANCELAR_ESCOLHER:{item.id}", label=_appointment_label(db, item)) for item in items]
        + [QuickReply(id="MENU:INICIO", label="Voltar")],
        interpreted_as="CANCELAR" if interpreted else None,
    )


def _start_reagendar(
    db: Session,
    empresa: Empresa,
    cliente: Cliente,
    settings: AICompanySettings,
    session: AIAttendanceSession,
    *,
    interpreted: bool,
) -> GuidedAgentResult:
    if not settings.pode_reagendar:
        return _base_result(db, cliente=cliente, settings=settings, session=session, text="O reagendamento automático está desativado.", options=_menu_options(settings), intent="REAGENDAR")
    items = _active_appointments(db, empresa.id, cliente.id)
    _save_flow(db, session, state="REAGENDAR_ESCOLHER", intent="REAGENDAR", context={"fluxo": "REAGENDAR"}, clear_pending=True)
    prefix = _interpret_prefix(settings, "reagendar um atendimento") if interpreted else ""
    if not items:
        return _base_result(db, cliente=cliente, settings=settings, session=session, text=prefix + "Não encontrei agendamentos ativos para reagendar.", options=_menu_options(settings), interpreted_as="REAGENDAR" if interpreted else None)
    return _base_result(
        db,
        cliente=cliente,
        settings=settings,
        session=session,
        text=prefix + "Qual agendamento você quer reagendar?",
        options=[QuickReply(id=f"REAGENDAR_ESCOLHER:{item.id}", label=_appointment_label(db, item)) for item in items]
        + [QuickReply(id="MENU:INICIO", label="Voltar")],
        interpreted_as="REAGENDAR" if interpreted else None,
    )


def _transfer(
    db: Session,
    empresa: Empresa,
    cliente: Cliente,
    base_config: ConfigIA | None,
    settings: AICompanySettings,
    session: AIAttendanceSession,
    reason: str,
) -> GuidedAgentResult:
    executor = _executor(db, empresa, cliente, settings, session, "quero falar com um atendente")
    trace: list[AgentToolTrace] = []
    _trace_tool(executor, trace, "transferir_para_humano", {"motivo": reason, "categoria": "SOLICITADO_CLIENTE"})
    session = _session(db, empresa_id=empresa.id, external_id=session.external_id, cliente_id=cliente.id, canal=session.canal)
    return _base_result(
        db,
        cliente=cliente,
        settings=settings,
        session=session,
        text=_transfer_message(empresa, base_config, settings, cliente),
        options=[],
        intent=session.last_intent,
        trace=trace,
    )


def _handle_menu_action(
    action: str,
    db: Session,
    empresa: Empresa,
    cliente: Cliente,
    base_config: ConfigIA | None,
    settings: AICompanySettings,
    session: AIAttendanceSession,
) -> GuidedAgentResult:
    if action in {"INICIO", "MENU"}:
        return _menu(db, empresa, cliente, base_config, settings, session, "", interpreted_as=None)
    if action == "AGENDAR":
        return _start_agendar(db, empresa, cliente, settings, session, interpreted=False)
    if action == "CONSULTAR_AGENDAMENTO":
        return _start_consult(db, empresa, cliente, settings, session, interpreted=False)
    if action == "CANCELAR":
        return _start_cancel(db, empresa, cliente, settings, session, interpreted=False)
    if action == "REAGENDAR":
        return _start_reagendar(db, empresa, cliente, settings, session, interpreted=False)
    if action == "SERVICOS_PRECOS":
        return _start_services(db, empresa, cliente, settings, session, interpreted=False)
    if action == "HUMANO":
        return _transfer(db, empresa, cliente, base_config, settings, session, "Cliente escolheu falar com um atendente no menu rápido.")
    return _menu(db, empresa, cliente, base_config, settings, session, "", interpreted_as=None)


def _handle_action(
    action_id: str,
    db: Session,
    empresa: Empresa,
    cliente: Cliente,
    base_config: ConfigIA | None,
    settings: AICompanySettings,
    session: AIAttendanceSession,
) -> GuidedAgentResult:
    if action_id.startswith("MENU:"):
        return _handle_menu_action(action_id.split(":", 1)[1], db, empresa, cliente, base_config, settings, session)

    if action_id.startswith("SERVICO_INFO:"):
        service_id = int(action_id.split(":", 1)[1])
        service = db.scalar(select(Servico).where(Servico.id == service_id, Servico.empresa_id == empresa.id, Servico.ativo.is_(True)))
        if service is None:
            return _start_services(db, empresa, cliente, settings, session, interpreted=False)
        description = f" — {service.descricao.strip()}" if service.descricao else ""
        text = f"{service.nome}: a partir de {_money(service.preco)}, duração aproximada de {service.duracao_minutos} min{description}"
        options = [QuickReply(id=f"AGENDAR_SERVICO:{service.id}", label="Agendar este serviço")]
        options.append(QuickReply(id="MENU:SERVICOS_PRECOS", label="Ver outros serviços"))
        options.append(QuickReply(id="MENU:INICIO", label="Voltar ao início"))
        return _base_result(db, cliente=cliente, settings=settings, session=session, text=text, options=options, intent="SERVICOS_PRECOS")

    if action_id.startswith("AGENDAR_SERVICO:"):
        return _after_service_selected(db, empresa, cliente, settings, session, int(action_id.split(":", 1)[1]))

    if action_id == "VEICULO:NOVO":
        context = dict(session.flow_context or {})
        _save_flow(db, session, state="AGENDAR_VEICULO_NOVO", intent="AGENDAR", context=context)
        return _base_result(db, cliente=cliente, settings=settings, session=session, text="Me diga qual é o veículo. Ex.: “Civic sedan 2020 preto”.", options=[QuickReply(id="MENU:INICIO", label="Voltar")])

    if action_id.startswith("AGENDAR_VEICULO:"):
        context = dict(session.flow_context or {})
        context["veiculo_id"] = int(action_id.split(":", 1)[1])
        return _ask_date(db, empresa, cliente, settings, session, context, "AGENDAR")

    if action_id.startswith("AGENDAR_DATA:"):
        value = action_id.split(":", 1)[1]
        if value == "DIGITAR":
            _save_flow(db, session, state="AGENDAR_DATA", intent="AGENDAR", context=dict(session.flow_context or {}))
            return _base_result(db, cliente=cliente, settings=settings, session=session, text="Pode escrever a data, por exemplo “sexta”, “amanhã” ou “25/08”.", options=[QuickReply(id="MENU:INICIO", label="Voltar")])
        return _availability_for_date(db, empresa, cliente, settings, session, date.fromisoformat(value), flow="AGENDAR")

    if action_id.startswith("AGENDAR_HORA:"):
        hour = action_id.split(":", 1)[1]
        context = dict(session.flow_context or {})
        if hour not in context.get("horarios_oferecidos", []):
            return _availability_for_date(db, empresa, cliente, settings, session, date.fromisoformat(str(context["data"])), flow="AGENDAR")
        executor = _executor(db, empresa, cliente, settings, session, "quero esse horário")
        trace: list[AgentToolTrace] = []
        result = _trace_tool(executor, trace, "preparar_agendamento", {
            "servico_id": int(context["servico_id"]),
            "veiculo_id": context.get("veiculo_id"),
            "data": str(context["data"]),
            "hora_inicio": hour,
        })
        if not result.get("ok") or not result.get("preparado", False):
            return _base_result(db, cliente=cliente, settings=settings, session=session, text=str(result.get("erro") or "Ainda faltam informações para concluir o agendamento."), options=[QuickReply(id="MENU:INICIO", label="Voltar ao início"), QuickReply(id="MENU:HUMANO", label="Falar com atendente")], trace=trace)
        text = f"Confira antes de confirmar:\n{result.get('servico')}\n{result.get('veiculo') or 'Veículo não informado'}\n{result.get('data')} às {result.get('hora')}\n{result.get('valor_final')}"
        return _base_result(db, cliente=cliente, settings=settings, session=session, text=text, options=[QuickReply(id="CONFIRMAR:AGENDAR", label="Confirmar agendamento", kind="primary"), QuickReply(id=f"AGENDAR_DATA:{context['data']}", label="Escolher outro horário"), QuickReply(id="MENU:INICIO", label="Cancelar e voltar")], trace=trace)

    if action_id == "CONFIRMAR:AGENDAR":
        executor = _executor(db, empresa, cliente, settings, session, "sim, pode confirmar")
        trace: list[AgentToolTrace] = []
        result = _trace_tool(executor, trace, "confirmar_agendamento", {})
        session = _session(db, empresa_id=empresa.id, external_id=session.external_id, cliente_id=cliente.id, canal=session.canal)
        if not result.get("ok"):
            return _base_result(db, cliente=cliente, settings=settings, session=session, text=str(result.get("erro") or "Não consegui confirmar o agendamento."), options=[QuickReply(id="MENU:HUMANO", label="Falar com atendente"), QuickReply(id="MENU:INICIO", label="Voltar")], trace=trace)
        _save_flow(db, session, state="MENU", intent="AGENDAMENTO_CONFIRMADO", context=None)
        return _base_result(db, cliente=cliente, settings=settings, session=session, text=f"Agendamento confirmado! {result.get('servico')} em {result.get('data')} às {result.get('hora')}. Valor {result.get('valor_final')}.", options=_menu_options(settings), trace=trace)

    if action_id.startswith("AGENDAMENTO_VER:"):
        appointment_id = int(action_id.split(":", 1)[1])
        item = db.scalar(select(Agendamento).where(Agendamento.id == appointment_id, Agendamento.empresa_id == empresa.id, Agendamento.cliente_id == cliente.id))
        if item is None:
            return _start_consult(db, empresa, cliente, settings, session, interpreted=False)
        service = db.scalar(select(Servico).where(Servico.id == item.servico_id))
        vehicle = db.scalar(select(Veiculo).where(Veiculo.id == item.veiculo_id)) if item.veiculo_id else None
        text = f"{service.nome if service else 'Serviço'}\n{item.data.strftime('%d/%m/%Y')} às {item.hora_inicio.strftime('%H:%M')}\nStatus: {item.status.value}\nValor: {_money(item.valor_final or item.valor_base)}"
        if vehicle:
            text += f"\nVeículo: {_vehicle_label(vehicle)}"
        options = []
        if settings.pode_reagendar:
            options.append(QuickReply(id=f"REAGENDAR_ESCOLHER:{item.id}", label="Reagendar"))
        if settings.pode_cancelar:
            options.append(QuickReply(id=f"CANCELAR_ESCOLHER:{item.id}", label="Cancelar"))
        options.append(QuickReply(id="MENU:INICIO", label="Voltar ao início"))
        return _base_result(db, cliente=cliente, settings=settings, session=session, text=text, options=options, intent="CONSULTAR_AGENDAMENTO")

    if action_id.startswith("CANCELAR_ESCOLHER:"):
        appointment_id = int(action_id.split(":", 1)[1])
        executor = _executor(db, empresa, cliente, settings, session, "quero cancelar")
        trace: list[AgentToolTrace] = []
        result = _trace_tool(executor, trace, "preparar_cancelamento", {"agendamento_id": appointment_id})
        if not result.get("ok"):
            return _base_result(db, cliente=cliente, settings=settings, session=session, text=str(result.get("erro") or "Não consegui preparar o cancelamento."), options=_menu_options(settings), trace=trace)
        return _base_result(db, cliente=cliente, settings=settings, session=session, text=f"Você quer cancelar {result.get('servico')} de {result.get('data')} às {result.get('hora')}?", options=[QuickReply(id="CONFIRMAR:CANCELAR", label="Sim, cancelar", kind="danger"), QuickReply(id="MENU:INICIO", label="Não, voltar")], trace=trace)

    if action_id == "CONFIRMAR:CANCELAR":
        executor = _executor(db, empresa, cliente, settings, session, "sim, pode cancelar")
        trace: list[AgentToolTrace] = []
        result = _trace_tool(executor, trace, "confirmar_cancelamento", {})
        session = _session(db, empresa_id=empresa.id, external_id=session.external_id, cliente_id=cliente.id, canal=session.canal)
        if not result.get("ok"):
            return _base_result(db, cliente=cliente, settings=settings, session=session, text=str(result.get("erro") or "Não consegui cancelar."), options=_menu_options(settings), trace=trace)
        _save_flow(db, session, state="MENU", intent="CANCELAMENTO_CONFIRMADO", context=None)
        return _base_result(db, cliente=cliente, settings=settings, session=session, text="Agendamento cancelado com sucesso.", options=_menu_options(settings), trace=trace)

    if action_id.startswith("REAGENDAR_ESCOLHER:"):
        appointment_id = int(action_id.split(":", 1)[1])
        item = db.scalar(select(Agendamento).where(Agendamento.id == appointment_id, Agendamento.empresa_id == empresa.id, Agendamento.cliente_id == cliente.id))
        if item is None:
            return _start_reagendar(db, empresa, cliente, settings, session, interpreted=False)
        context = {"fluxo": "REAGENDAR", "agendamento_id": item.id, "servico_id": item.servico_id}
        return _ask_date(db, empresa, cliente, settings, session, context, "REAGENDAR")

    if action_id.startswith("REAGENDAR_DATA:"):
        value = action_id.split(":", 1)[1]
        if value == "DIGITAR":
            _save_flow(db, session, state="REAGENDAR_DATA", intent="REAGENDAR", context=dict(session.flow_context or {}))
            return _base_result(db, cliente=cliente, settings=settings, session=session, text="Escreva a nova data, por exemplo “sexta” ou “25/08”.", options=[QuickReply(id="MENU:INICIO", label="Voltar")])
        return _availability_for_date(db, empresa, cliente, settings, session, date.fromisoformat(value), flow="REAGENDAR")

    if action_id.startswith("REAGENDAR_HORA:"):
        hour = action_id.split(":", 1)[1]
        context = dict(session.flow_context or {})
        executor = _executor(db, empresa, cliente, settings, session, "quero esse novo horário")
        trace: list[AgentToolTrace] = []
        result = _trace_tool(executor, trace, "preparar_reagendamento", {
            "agendamento_id": int(context["agendamento_id"]),
            "data": str(context["data"]),
            "hora_inicio": hour,
        })
        if not result.get("ok"):
            return _base_result(db, cliente=cliente, settings=settings, session=session, text=str(result.get("erro") or "Não consegui preparar o reagendamento."), options=_menu_options(settings), trace=trace)
        return _base_result(db, cliente=cliente, settings=settings, session=session, text=f"Confirmar a mudança para {result.get('nova_data')} às {result.get('nova_hora')}?", options=[QuickReply(id="CONFIRMAR:REAGENDAR", label="Confirmar reagendamento", kind="primary"), QuickReply(id=f"REAGENDAR_DATA:{context['data']}", label="Escolher outro horário"), QuickReply(id="MENU:INICIO", label="Voltar")], trace=trace)

    if action_id == "CONFIRMAR:REAGENDAR":
        executor = _executor(db, empresa, cliente, settings, session, "sim, pode reagendar")
        trace: list[AgentToolTrace] = []
        result = _trace_tool(executor, trace, "confirmar_reagendamento", {})
        session = _session(db, empresa_id=empresa.id, external_id=session.external_id, cliente_id=cliente.id, canal=session.canal)
        if not result.get("ok"):
            return _base_result(db, cliente=cliente, settings=settings, session=session, text=str(result.get("erro") or "Não consegui reagendar."), options=_menu_options(settings), trace=trace)
        _save_flow(db, session, state="MENU", intent="REAGENDAMENTO_CONFIRMADO", context=None)
        return _base_result(db, cliente=cliente, settings=settings, session=session, text=f"Reagendamento confirmado para {result.get('data')} às {result.get('hora')}.", options=_menu_options(settings), trace=trace)

    return _menu(db, empresa, cliente, base_config, settings, session, "", interpreted_as=None)


def _contextual_options_from_agent(result: AIAgentResult, settings: AICompanySettings) -> list[QuickReply]:
    if result.handoff:
        return []
    pending = result.pending_action or {}
    if pending.get("type") == "AGENDAR":
        return [QuickReply(id="CONFIRMAR:AGENDAR", label="Confirmar agendamento", kind="primary"), QuickReply(id="MENU:INICIO", label="Voltar ao início")]
    if pending.get("type") == "CANCELAR":
        return [QuickReply(id="CONFIRMAR:CANCELAR", label="Sim, cancelar", kind="danger"), QuickReply(id="MENU:INICIO", label="Não, voltar")]
    if pending.get("type") == "REAGENDAR":
        return [QuickReply(id="CONFIRMAR:REAGENDAR", label="Confirmar reagendamento", kind="primary"), QuickReply(id="MENU:INICIO", label="Voltar")]
    return [QuickReply(id="MENU:INICIO", label="Voltar ao início"), QuickReply(id="MENU:HUMANO", label="Falar com atendente")]


def run_guided_agent(
    db: Session,
    *,
    empresa_id: int,
    cliente_id: int,
    session_id: str,
    transcript: list[tuple[str, str]],
    action_id: str | None = None,
    canal: str = "WHATSAPP_SIMULADO",
) -> GuidedAgentResult:
    empresa = db.scalar(select(Empresa).where(Empresa.id == empresa_id, Empresa.ativo.is_(True)))
    cliente = db.scalar(select(Cliente).where(Cliente.id == cliente_id, Cliente.empresa_id == empresa_id))
    if empresa is None or cliente is None:
        raise RuntimeError("Empresa ou cliente não está disponível para o atendimento.")

    settings = _settings(db, empresa_id)
    base_config = db.scalar(select(ConfigIA).where(ConfigIA.empresa_id == empresa_id))
    session = _session(db, empresa_id=empresa_id, external_id=session_id, cliente_id=cliente_id, canal=canal)

    if session.estado == "HUMANO":
        _, complete = _known_customer(db, cliente, settings)
        return GuidedAgentResult(
            text=_transfer_message(empresa, base_config, settings, cliente),
            model="flowdesk-guided",
            response_id=None,
            tool_trace=[],
            intent=session.last_intent,
            state=session.estado,
            handoff=True,
            handoff_reason=session.handoff_motivo,
            customer_id=cliente.id,
            customer_complete=complete,
            pending_action=session.pending_action,
            options=[],
        )

    if action_id and settings.fluxo_guiado_ativo:
        return _handle_action(action_id, db, empresa, cliente, base_config, settings, session)

    if not transcript or transcript[-1][0] != "CLIENTE":
        raise RuntimeError("A última mensagem precisa ser do cliente.")
    user_text = transcript[-1][1].strip()

    if settings.fluxo_guiado_ativo:
        if _is_menu_request(user_text) or _greeting_phrase(user_text):
            return _menu(db, empresa, cliente, base_config, settings, session, user_text)

        state = session.estado
        context = dict(session.flow_context or {})

        if state == "AGENDAR_CLIENTE_NOME":
            if len(user_text) >= 2 and len(user_text) <= 150:
                executor = _executor(db, empresa, cliente, settings, session, user_text)
                trace: list[AgentToolTrace] = []
                result = _trace_tool(executor, trace, "atualizar_cliente", {"nome": user_text, "email": None, "observacoes": None})
                if result.get("ok"):
                    if "email" in (settings.campos_cliente_obrigatorios or []) and not cliente.email:
                        _save_flow(db, session, state="AGENDAR_CLIENTE_EMAIL", intent="AGENDAR", context=context)
                        return _base_result(db, cliente=cliente, settings=settings, session=session, text=f"Prazer, {cliente.nome.split()[0]}! Qual é o seu e-mail?", options=[QuickReply(id="MENU:INICIO", label="Voltar")], trace=trace)
                    guided = _choose_vehicle(db, empresa, cliente, settings, session, context)
                    return GuidedAgentResult(**{**guided.__dict__, "tool_trace": trace + guided.tool_trace})

        if state == "AGENDAR_CLIENTE_EMAIL":
            if "@" in user_text and "." in user_text:
                executor = _executor(db, empresa, cliente, settings, session, user_text)
                trace: list[AgentToolTrace] = []
                result = _trace_tool(executor, trace, "atualizar_cliente", {"nome": None, "email": user_text, "observacoes": None})
                if result.get("ok"):
                    guided = _choose_vehicle(db, empresa, cliente, settings, session, context)
                    return GuidedAgentResult(**{**guided.__dict__, "tool_trace": trace + guided.tool_trace})
            return _base_result(db, cliente=cliente, settings=settings, session=session, text="Não consegui identificar um e-mail válido. Pode enviar novamente?", options=[QuickReply(id="MENU:INICIO", label="Voltar")])

        if state == "AGENDAR_VEICULO_NOVO":
            result = run_operational_agent(db, empresa_id=empresa_id, cliente_id=cliente_id, session_id=session_id, transcript=transcript, canal=canal)
            vehicles = _vehicles(db, cliente.id)
            created_ids = [
                item.result.get("veiculo_id")
                for item in result.tool_trace
                if item.name == "cadastrar_veiculo" and item.result.get("ok") and item.result.get("veiculo_id")
            ]
            if created_ids:
                context["veiculo_id"] = int(created_ids[-1])
                guided = _ask_date(db, empresa, cliente, settings, session, context, "AGENDAR")
                return GuidedAgentResult(**{**guided.__dict__, "tool_trace": result.tool_trace + guided.tool_trace, "model": result.model, "response_id": result.response_id})
            if len(vehicles) == 1 and vehicles[0].id:
                context["veiculo_id"] = vehicles[0].id
            return _from_agent(result, _contextual_options_from_agent(result, settings))

        if state in {"AGENDAR_DATA", "REAGENDAR_DATA"}:
            target = _parse_user_date(user_text, _local_now(empresa).date())
            if target:
                return _availability_for_date(db, empresa, cliente, settings, session, target, flow="AGENDAR" if state == "AGENDAR_DATA" else "REAGENDAR")
            return _base_result(db, cliente=cliente, settings=settings, session=session, text="Entendi que você está informando a data, mas não consegui identificar qual dia. Você pode escrever “amanhã”, “sexta” ou “25/08”.", options=_date_options("AGENDAR_DATA" if state == "AGENDAR_DATA" else "REAGENDAR_DATA", empresa))

        if state in {"AGENDAR_HORARIO", "REAGENDAR_HORARIO"}:
            hour = _parse_user_time(user_text)
            offered = context.get("horarios_oferecidos", [])
            if hour and hour in offered:
                return _handle_action(("AGENDAR_HORA:" if state == "AGENDAR_HORARIO" else "REAGENDAR_HORA:") + hour, db, empresa, cliente, base_config, settings, session)
            options = [QuickReply(id=("AGENDAR_HORA:" if state == "AGENDAR_HORARIO" else "REAGENDAR_HORA:") + str(item), label=str(item)) for item in offered[:6]]
            options.append(QuickReply(id="MENU:INICIO", label="Voltar"))
            return _base_result(db, cliente=cliente, settings=settings, session=session, text="Não identifiquei esse horário entre as opções disponíveis. Qual destes você prefere?", options=options)

        intent = _infer_standard_intent(user_text)
        if intent == "HUMANO":
            return _transfer(db, empresa, cliente, base_config, settings, session, "Cliente pediu atendimento humano por mensagem livre.")
        if intent == "AGENDAR":
            return _start_agendar(db, empresa, cliente, settings, session, interpreted=True)
        if intent == "CONSULTAR_AGENDAMENTO":
            return _start_consult(db, empresa, cliente, settings, session, interpreted=True)
        if intent == "CANCELAR":
            return _start_cancel(db, empresa, cliente, settings, session, interpreted=True)
        if intent == "REAGENDAR":
            return _start_reagendar(db, empresa, cliente, settings, session, interpreted=True)
        if intent == "SERVICOS_PRECOS":
            return _start_services(db, empresa, cliente, settings, session, interpreted=True)

    result = run_operational_agent(
        db,
        empresa_id=empresa_id,
        cliente_id=cliente_id,
        session_id=session_id,
        transcript=transcript,
        canal=canal,
    )
    return _from_agent(result, _contextual_options_from_agent(result, settings))
