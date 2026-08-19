from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import replace
from difflib import SequenceMatcher
from typing import Any

from openai import APIConnectionError, APIError, OpenAI, RateLimitError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.models.models import Cliente, ConfigIA, Empresa
from app.services.ai_agent import (
    AgentToolTrace,
    _Executor,
    _session,
    _settings,
    _transfer_message,
)
from app.services.ai_guided_flow import (
    GuidedAgentResult,
    QuickReply,
    _ask_date,
    _base_result,
    run_guided_agent,
)


# Catálogo local para os modelos mais comuns no Brasil. Ele existe para que
# mensagens simples como "Corsa", "corola" ou "corssa" não dependam de uma
# chamada ao provedor de IA. Quando o modelo não está aqui, o fallback
# semântico continua assumindo a interpretação.
_COMMON_VEHICLES: list[tuple[str, str, str]] = [
    ("toyota", "corolla", "SEDAN"),
    ("toyota", "etios", "HATCH"),
    ("toyota", "yaris", "HATCH"),
    ("toyota", "hilux", "CAMINHONETE"),
    ("toyota", "sw4", "SUV"),
    ("honda", "civic", "SEDAN"),
    ("honda", "city", "SEDAN"),
    ("honda", "fit", "HATCH"),
    ("honda", "hr-v", "SUV"),
    ("honda", "hrv", "SUV"),
    ("honda", "wr-v", "SUV"),
    ("honda", "wrv", "SUV"),
    ("chevrolet", "corsa", "HATCH"),
    ("chevrolet", "corsa sedan", "SEDAN"),
    ("chevrolet", "classic", "SEDAN"),
    ("chevrolet", "celta", "HATCH"),
    ("chevrolet", "prisma", "SEDAN"),
    ("chevrolet", "onix", "HATCH"),
    ("chevrolet", "onix plus", "SEDAN"),
    ("chevrolet", "cruze", "SEDAN"),
    ("chevrolet", "astra", "HATCH"),
    ("chevrolet", "vectra", "SEDAN"),
    ("chevrolet", "tracker", "SUV"),
    ("chevrolet", "spin", "OUTRO"),
    ("chevrolet", "montana", "CAMINHONETE"),
    ("chevrolet", "s10", "CAMINHONETE"),
    ("volkswagen", "gol", "HATCH"),
    ("volkswagen", "fox", "HATCH"),
    ("volkswagen", "polo", "HATCH"),
    ("volkswagen", "voyage", "SEDAN"),
    ("volkswagen", "virtus", "SEDAN"),
    ("volkswagen", "jetta", "SEDAN"),
    ("volkswagen", "t-cross", "SUV"),
    ("volkswagen", "tcross", "SUV"),
    ("volkswagen", "nivus", "SUV"),
    ("volkswagen", "taos", "SUV"),
    ("volkswagen", "saveiro", "CAMINHONETE"),
    ("fiat", "uno", "HATCH"),
    ("fiat", "mobi", "HATCH"),
    ("fiat", "palio", "HATCH"),
    ("fiat", "punto", "HATCH"),
    ("fiat", "argo", "HATCH"),
    ("fiat", "siena", "SEDAN"),
    ("fiat", "grand siena", "SEDAN"),
    ("fiat", "cronos", "SEDAN"),
    ("fiat", "pulse", "SUV"),
    ("fiat", "fastback", "SUV"),
    ("fiat", "toro", "CAMINHONETE"),
    ("fiat", "strada", "CAMINHONETE"),
    ("hyundai", "hb20", "HATCH"),
    ("hyundai", "hb20s", "SEDAN"),
    ("hyundai", "creta", "SUV"),
    ("hyundai", "tucson", "SUV"),
    ("jeep", "renegade", "SUV"),
    ("jeep", "compass", "SUV"),
    ("jeep", "commander", "SUV"),
    ("ford", "ka", "HATCH"),
    ("ford", "fiesta", "HATCH"),
    ("ford", "focus", "HATCH"),
    ("ford", "ecosport", "SUV"),
    ("ford", "territory", "SUV"),
    ("ford", "ranger", "CAMINHONETE"),
    ("renault", "kwid", "HATCH"),
    ("renault", "sandero", "HATCH"),
    ("renault", "logan", "SEDAN"),
    ("renault", "duster", "SUV"),
    ("renault", "oroch", "CAMINHONETE"),
    ("nissan", "march", "HATCH"),
    ("nissan", "versa", "SEDAN"),
    ("nissan", "sentra", "SEDAN"),
    ("nissan", "kicks", "SUV"),
    ("nissan", "frontier", "CAMINHONETE"),
    ("peugeot", "206", "HATCH"),
    ("peugeot", "207", "HATCH"),
    ("peugeot", "208", "HATCH"),
    ("peugeot", "2008", "SUV"),
    ("citroen", "c3", "HATCH"),
    ("citroen", "c4 cactus", "SUV"),
    ("kia", "sportage", "SUV"),
    ("mitsubishi", "pajero", "SUV"),
    ("mitsubishi", "l200", "CAMINHONETE"),
]


# Algumas famílias tiveram mais de uma carroceria. Para o atendimento rápido,
# aceitamos a forma mais comum quando o cliente escreve somente o modelo, mas
# respeitamos qualificadores explícitos. Isso evita perguntar "hatch ou sedan?"
# sem necessidade na maioria dos atendimentos.
_EXACT_VEHICLE_ALIASES: dict[str, tuple[str, str, str]] = {
    "corsa": ("chevrolet", "corsa", "HATCH"),
    "corsa hatch": ("chevrolet", "corsa", "HATCH"),
    "corsa sedan": ("chevrolet", "corsa", "SEDAN"),
    "corsa classic": ("chevrolet", "classic", "SEDAN"),
    "classic": ("chevrolet", "classic", "SEDAN"),
    "onix plus": ("chevrolet", "onix plus", "SEDAN"),
    "hb20s": ("hyundai", "hb20s", "SEDAN"),
    "grand siena": ("fiat", "grand siena", "SEDAN"),
}


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower())
    text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-z0-9-]+", " ", text).split())


def _strip_vehicle_filler(value: str) -> str:
    text = _normalize(value)
    fillers = (
        "meu carro e ",
        "meu carro é ",
        "o carro e ",
        "o carro é ",
        "e um ",
        "é um ",
        "eh um ",
        "tenho um ",
        "tenho uma ",
        "um ",
        "uma ",
    )
    for prefix in fillers:
        prefix = _normalize(prefix)
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    return text


def _local_vehicle_guess(value: str) -> dict[str, Any] | None:
    text = _strip_vehicle_filler(value)
    if not text:
        return None

    # Ano é irrelevante para o fluxo. Removê-lo também melhora a comparação
    # quando o cliente escreve algo como "Corsa 2008".
    text_without_year = " ".join(
        token for token in text.split() if not re.fullmatch(r"(?:19|20)\d{2}", token)
    ).strip()
    alias = _EXACT_VEHICLE_ALIASES.get(text_without_year)
    if alias is not None:
        brand, model, vehicle_type = alias
        return {
            "identificavel": True,
            "marca": brand.title(),
            "modelo": model.title(),
            "tipo_veiculo": vehicle_type,
            "cor": None,
            "confianca": "ALTA",
            "interpretacao": f"{brand.title()} {model.title()}",
            "pergunta": None,
            "origem_interpretacao": "alias-local",
            "score": 1.0,
        }

    tokens = text_without_year.split() or text.split()
    candidates: list[tuple[float, str, str, str]] = []
    for brand, model, vehicle_type in _COMMON_VEHICLES:
        model_norm = _normalize(model)
        brand_norm = _normalize(brand)
        best_model = max(
            [SequenceMatcher(None, token, model_norm).ratio() for token in tokens] +
            [SequenceMatcher(None, text_without_year or text, model_norm).ratio()]
        )
        brand_bonus = 0.08 if brand_norm in text else 0.0
        score = min(1.0, best_model + brand_bonus)
        candidates.append((score, brand, model, vehicle_type))
    candidates.sort(reverse=True)
    best = candidates[0]
    second = candidates[1] if len(candidates) > 1 else (0.0, "", "", "")
    # Ex.: corola -> corolla; corssa -> corsa. Exigimos distância razoável do
    # segundo candidato, exceto quando a correspondência do modelo é quase exata.
    if best[0] >= 0.78 and (best[0] - second[0] >= 0.08 or best[0] >= 0.90):
        return {
            "identificavel": True,
            "marca": best[1].title(),
            "modelo": best[2].title(),
            "tipo_veiculo": best[3],
            "cor": None,
            "confianca": "ALTA" if best[0] >= 0.90 else "MEDIA",
            "interpretacao": f"{best[1].title()} {best[2].title()}",
            "pergunta": None,
            "origem_interpretacao": "fuzzy-local",
            "score": round(best[0], 3),
        }
    return None


def _semantic_vehicle_guess(value: str) -> dict[str, Any] | None:
    if not app_settings.openai_api_key:
        return None
    client = OpenAI(
        api_key=app_settings.openai_api_key,
        timeout=app_settings.openai_timeout_seconds,
    )
    tool = {
        "type": "function",
        "name": "interpretar_veiculo",
        "description": "Interpreta de forma tolerante o veículo mencionado pelo cliente.",
        "parameters": {
            "type": "object",
            "properties": {
                "identificavel": {"type": "boolean"},
                "marca": {"type": ["string", "null"]},
                "modelo": {"type": ["string", "null"]},
                "tipo_veiculo": {
                    "type": ["string", "null"],
                    "enum": ["HATCH", "SEDAN", "SUV", "CAMINHONETE", "OUTRO", None],
                },
                "cor": {"type": ["string", "null"]},
                "confianca": {"type": "string", "enum": ["ALTA", "MEDIA", "BAIXA"]},
                "interpretacao": {"type": ["string", "null"]},
                "pergunta": {"type": ["string", "null"]},
            },
            "required": [
                "identificavel",
                "marca",
                "modelo",
                "tipo_veiculo",
                "cor",
                "confianca",
                "interpretacao",
                "pergunta",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    }
    instructions = """Você interpreta veículos em conversas brasileiras de WhatsApp.
Seu objetivo é entender linguagem humana, não validar um formulário. Um nome de modelo conhecido sozinho já é informação suficiente para identificar um veículo na maioria dos casos.
Seja tolerante a abreviações, ausência de acentos, erros de digitação, nomes incompletos e marca omitida. Use conhecimento automotivo geral para normalizar marca/modelo e inferir o TIPO do veículo sem perguntar isso ao cliente.
Exemplos: 'corola' normalmente significa Toyota Corolla SEDAN; 'civc' pode ser Honda Civic SEDAN; 'hilux' significa Toyota Hilux CAMINHONETE; 'corsa' deve ser tratado por padrão como Chevrolet Corsa HATCH; 'corsa sedan' ou 'classic' devem ser SEDAN.
NÃO exija ano. Ano não é necessário para este fluxo e não existe campo de ano na resposta.
Se um modelo teve mais de uma carroceria e o cliente não especificou a variante, prefira a versão mais comum/plausível no Brasil e siga com confiança MEDIA, em vez de interromper o atendimento. Se ele especificar hatch, sedan, SUV ou picape, respeite o qualificador.
Se houver uma interpretação única e plausível, prefira seguir com confiança MEDIA/ALTA em vez de pedir confirmação por perfeccionismo.
Só use BAIXA e faça uma pergunta curta quando realmente houver mais de uma interpretação plausível que possa mudar materialmente o atendimento ou quando nenhum veículo for identificável.
Não invente placa nem informação pessoal."""
    try:
        response = client.responses.create(
            model=app_settings.openai_model,
            instructions=instructions,
            input=f"Mensagem do cliente: {value}",
            tools=[tool],
            tool_choice="required",
            parallel_tool_calls=False,
            max_output_tokens=220,
            store=False,
        )
    except (RateLimitError, APIConnectionError, APIError):
        return None
    for item in response.output:
        if getattr(item, "type", None) != "function_call":
            continue
        try:
            data = json.loads(item.arguments or "{}")
        except json.JSONDecodeError:
            return None
        data["origem_interpretacao"] = "modelo"
        return data
    return None


def _interpret_vehicle(value: str) -> dict[str, Any] | None:
    local = _local_vehicle_guess(value)
    if local and local.get("confianca") == "ALTA":
        return local
    semantic = _semantic_vehicle_guess(value)
    if semantic and semantic.get("identificavel"):
        return semantic
    return semantic or local


def _vehicle_trace(interpretation: dict[str, Any]) -> AgentToolTrace:
    result = dict(interpretation)
    return AgentToolTrace(
        name="interpretar_veiculo",
        arguments={"texto_cliente": "[mensagem atual]"},
        result={"ok": True, **result},
    )


def _handle_vehicle_state(
    db: Session,
    *,
    empresa: Empresa,
    cliente: Cliente,
    session_id: str,
    user_text: str,
    canal: str,
) -> GuidedAgentResult:
    company_settings = _settings(db, empresa.id)
    session = _session(
        db,
        empresa_id=empresa.id,
        external_id=session_id,
        cliente_id=cliente.id,
        canal=canal,
    )
    base_config = db.scalar(select(ConfigIA).where(ConfigIA.empresa_id == empresa.id))
    interpretation = _interpret_vehicle(user_text)
    trace: list[AgentToolTrace] = []
    if interpretation:
        trace.append(_vehicle_trace(interpretation))

    if (
        interpretation
        and interpretation.get("identificavel")
        and interpretation.get("modelo")
        and interpretation.get("confianca") in {"ALTA", "MEDIA"}
    ):
        executor = _Executor(
            db=db,
            empresa=empresa,
            cliente=cliente,
            company_settings=company_settings,
            session=session,
            latest_user_text=user_text,
        )
        args = {
            "tipo_veiculo": interpretation.get("tipo_veiculo"),
            "marca": interpretation.get("marca"),
            "modelo": interpretation.get("modelo"),
            "ano": None,
            "cor": interpretation.get("cor"),
            "apelido": None,
        }
        result = executor.execute("cadastrar_veiculo", args)
        trace.append(AgentToolTrace(name="cadastrar_veiculo", arguments=args, result=result))
        if result.get("ok") and result.get("veiculo_id"):
            context = dict(session.flow_context or {})
            context["veiculo_id"] = int(result["veiculo_id"])
            guided = _ask_date(
                db,
                empresa,
                cliente,
                company_settings,
                session,
                context,
                "AGENDAR",
            )
            label = str(
                interpretation.get("interpretacao")
                or " ".join(
                    part for part in [interpretation.get("marca"), interpretation.get("modelo")]
                    if part
                )
            ).strip()
            prefix = f"Perfeito, entendi que é um {label}. " if label else "Perfeito. "
            return replace(
                guided,
                text=prefix + guided.text,
                tool_trace=trace + guided.tool_trace,
                model=("flowdesk-fuzzy" if interpretation.get("origem_interpretacao") in {"fuzzy-local", "alias-local"} else app_settings.openai_model),
                interpreted_as="VEICULO_IDENTIFICADO",
            )

    executor = _Executor(
        db=db,
        empresa=empresa,
        cliente=cliente,
        company_settings=company_settings,
        session=session,
        latest_user_text=user_text,
    )
    failure = executor.execute(
        "sinalizar_nao_entendimento",
        {
            "motivo": "Não foi possível identificar com segurança o modelo do veículo informado pelo cliente."
        },
    )
    trace.append(
        AgentToolTrace(
            name="sinalizar_nao_entendimento",
            arguments={"motivo": "veículo ambíguo"},
            result=failure,
        )
    )
    session = _session(
        db,
        empresa_id=empresa.id,
        external_id=session_id,
        cliente_id=cliente.id,
        canal=canal,
    )
    if session.estado == "HUMANO" or failure.get("transferido"):
        return _base_result(
            db,
            cliente=cliente,
            settings=company_settings,
            session=session,
            text=_transfer_message(empresa, base_config, company_settings, cliente),
            options=[],
            intent=session.last_intent,
            trace=trace,
            interpreted_as="VEICULO_NAO_IDENTIFICADO",
        )

    question = None
    if interpretation:
        question = interpretation.get("pergunta")
    question = question or "Não consegui identificar qual é o carro. Pode digitar o modelo novamente? Ex.: Corsa, Corolla, Civic, Onix ou Hilux."
    return _base_result(
        db,
        cliente=cliente,
        settings=company_settings,
        session=session,
        text=str(question),
        options=[
            QuickReply(id="MENU:INICIO", label="Voltar ao início", kind="secondary"),
            QuickReply(id="MENU:HUMANO", label="Falar com atendente", kind="human"),
        ],
        intent="AGENDAR",
        trace=trace,
        interpreted_as="VEICULO_NAO_IDENTIFICADO",
    )


def _remove_leading_greeting(value: str) -> tuple[str, str | None]:
    normalized = value.strip()
    match = re.match(
        r"^\s*(bom\s+dia|boa\s+tarde|boa\s+noite|oi|olá|ola|opa)\b[!,.:;\s-]*(.*)$",
        normalized,
        flags=re.IGNORECASE,
    )
    if not match:
        return normalized, None
    rest = match.group(2).strip()
    greeting = match.group(1)
    if not rest:
        return normalized, None
    return rest, greeting


def run_autonomous_guided_agent(
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

    session = _session(
        db,
        empresa_id=empresa_id,
        external_id=session_id,
        cliente_id=cliente_id,
        canal=canal,
    )
    if (
        not action_id
        and transcript
        and transcript[-1][0] == "CLIENTE"
        and session.estado == "AGENDAR_VEICULO_NOVO"
    ):
        return _handle_vehicle_state(
            db,
            empresa=empresa,
            cliente=cliente,
            session_id=session_id,
            user_text=transcript[-1][1],
            canal=canal,
        )

    adapted = list(transcript)
    leading_greeting: str | None = None
    if not action_id and adapted and adapted[-1][0] == "CLIENTE":
        stripped, leading_greeting = _remove_leading_greeting(adapted[-1][1])
        if leading_greeting and stripped:
            adapted[-1] = ("CLIENTE", stripped)

    try:
        result = run_guided_agent(
            db,
            empresa_id=empresa_id,
            cliente_id=cliente_id,
            session_id=session_id,
            transcript=adapted,
            action_id=action_id,
            canal=canal,
        )
        # O cadastro de veículo deve parecer uma conversa, não um formulário.
        if result.state == "AGENDAR_VEICULO_NOVO":
            result = replace(
                result,
                text="Qual é o seu carro? Pode escrever só o modelo, por exemplo: “Corsa”, “Corolla”, “Civic”, “Onix” ou “Hilux”.",
            )
        if leading_greeting and result.interpreted_as:
            result = replace(result, text=f"{leading_greeting.capitalize()}! {result.text}")
        return result
    except Exception:
        # Uma falha de interpretação nunca deve virar uma mensagem técnica para o
        # cliente. Mantemos o estado e damos um caminho de recuperação.
        company_settings = _settings(db, empresa_id)
        session = _session(
            db,
            empresa_id=empresa_id,
            external_id=session_id,
            cliente_id=cliente_id,
            canal=canal,
        )
        if session.estado == "AGENDAR_VEICULO_NOVO":
            text = "Não consegui identificar o veículo dessa vez. Pode escrever só o modelo novamente?"
        elif session.estado in {"AGENDAR_DATA", "REAGENDAR_DATA"}:
            text = "Não consegui identificar a data. Pode escrever de outro jeito, como “amanhã”, “sexta” ou “25/08”?"
        elif session.estado in {"AGENDAR_HORARIO", "REAGENDAR_HORARIO"}:
            text = "Não consegui identificar o horário. Pode escolher uma das opções ou escrever o horário novamente?"
        else:
            text = "Não consegui interpretar essa parte com segurança. Pode escrever de outro jeito ou escolher uma opção abaixo?"
        return _base_result(
            db,
            cliente=cliente,
            settings=company_settings,
            session=session,
            text=text,
            options=[
                QuickReply(id="MENU:INICIO", label="Voltar ao início", kind="secondary"),
                QuickReply(id="MENU:HUMANO", label="Falar com atendente", kind="human"),
            ],
            intent=session.last_intent,
            interpreted_as="RECUPERACAO_CONTEXTO",
        )