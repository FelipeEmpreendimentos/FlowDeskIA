from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from time import monotonic, perf_counter
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.permissions import is_management
from app.core.security import create_simulator_access_token, decode_access_token
from app.database.database import get_db
from app.models.enums import AtorLog
from app.models.models import ConfigIA, Empresa, Log, Usuario
from app.services.ai_conversation import (
    AIConversationStateError,
    AINotConfiguredError,
    AIProviderError,
    build_simulator_ai_context,
    request_openai,
)

router = APIRouter(prefix="/simulador-ia", tags=["Simulador IA"])

RATE_WINDOW_SECONDS = 10 * 60
RATE_MAX_MESSAGES = 30
_rate_buckets: dict[str, deque[float]] = defaultdict(deque)


class SimulatorLinkCreate(BaseModel):
    validade_dias: Literal[1, 7, 30] = 7


class SimulatorLinkOut(BaseModel):
    path: str
    expires_at: datetime
    validade_dias: int


class SimulatorBootstrapOut(BaseModel):
    empresa: str
    assistente: str
    mensagem_boas_vindas: str
    expires_at: datetime
    canal: str = "WHATSAPP_SIMULADO"


class SimulatorProfile(BaseModel):
    nome: str = Field(default="Cliente de teste", min_length=1, max_length=80)
    tipo_veiculo: str | None = Field(default=None, max_length=40)
    veiculo: str | None = Field(default=None, max_length=120)
    observacoes: str | None = Field(default=None, max_length=300)


class SimulatorHistoryMessage(BaseModel):
    remetente: Literal["CLIENTE", "IA"]
    conteudo: str = Field(min_length=1, max_length=1600)


class SimulatorReplyRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=100)
    perfil: SimulatorProfile
    mensagens: list[SimulatorHistoryMessage] = Field(min_length=1, max_length=20)


class SimulatorReplyOut(BaseModel):
    id_whatsapp: str
    remetente: Literal["IA"] = "IA"
    conteudo: str
    created_at: datetime
    model: str
    latency_ms: int
    status: Literal["ENTREGUE"] = "ENTREGUE"


def _public_link_payload(token: str) -> dict:
    try:
        payload = decode_access_token(token)
        if payload.get("kind") != "ai_simulator":
            raise ValueError
        empresa_id = int(payload["empresa_id"])
        if empresa_id <= 0:
            raise ValueError
        return payload
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Este link de simulação é inválido ou expirou.",
        ) from exc


def _company_for_token(db: Session, token: str) -> tuple[Empresa, dict]:
    payload = _public_link_payload(token)
    empresa = db.scalar(
        select(Empresa).where(
            Empresa.id == int(payload["empresa_id"]),
            Empresa.ativo.is_(True),
        )
    )
    if empresa is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Este link de simulação não está disponível.",
        )
    return empresa, payload


def _enforce_rate_limit(request: Request, token: str) -> None:
    client_ip = request.client.host if request.client else "unknown"
    token_fingerprint = sha256(token.encode("utf-8")).hexdigest()[:18]
    key = f"{token_fingerprint}:{client_ip}"
    now = monotonic()
    bucket = _rate_buckets[key]

    while bucket and now - bucket[0] > RATE_WINDOW_SECONDS:
        bucket.popleft()

    if len(bucket) >= RATE_MAX_MESSAGES:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Muitas mensagens de teste em pouco tempo. Aguarde alguns minutos e tente novamente.",
        )

    bucket.append(now)


def _expires_at(payload: dict) -> datetime:
    return datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)


@router.post(
    "/link",
    response_model=SimulatorLinkOut,
    status_code=status.HTTP_201_CREATED,
)
def gerar_link_simulador(
    data: SimulatorLinkCreate,
    current_user: Usuario = Depends(get_current_user),
) -> SimulatorLinkOut:
    if not is_management(current_user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Somente administradores e gerentes podem gerar links do simulador.",
        )

    token, expires_in = create_simulator_access_token(
        user_id=current_user.id,
        empresa_id=current_user.empresa_id,
        days=data.validade_dias,
    )
    return SimulatorLinkOut(
        path=f"/simulador/whatsapp/{token}",
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        validade_dias=data.validade_dias,
    )


@router.get("/public/{token}", response_model=SimulatorBootstrapOut)
def abrir_simulador(
    token: str,
    db: Session = Depends(get_db),
) -> SimulatorBootstrapOut:
    empresa, payload = _company_for_token(db, token)
    config = db.scalar(select(ConfigIA).where(ConfigIA.empresa_id == empresa.id))

    assistente = (
        config.nome_assistente.strip()
        if config and config.nome_assistente and config.nome_assistente.strip()
        else "Assistente"
    )
    boas_vindas = (
        config.mensagem_boas_vindas.strip()
        if config
        and config.mensagem_boas_vindas
        and config.mensagem_boas_vindas.strip()
        else f"Olá! 👋 Você está falando com {assistente}. Como posso ajudar?"
    )

    return SimulatorBootstrapOut(
        empresa=empresa.nome,
        assistente=assistente,
        mensagem_boas_vindas=boas_vindas,
        expires_at=_expires_at(payload),
    )


@router.post(
    "/public/{token}/responder",
    response_model=SimulatorReplyOut,
)
def responder_no_simulador(
    token: str,
    data: SimulatorReplyRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> SimulatorReplyOut:
    empresa, _payload = _company_for_token(db, token)
    _enforce_rate_limit(request, token)

    if data.mensagens[-1].remetente != "CLIENTE":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A última mensagem do simulador precisa ser do cliente.",
        )

    transcript = [
        (
            "CLIENTE" if item.remetente == "CLIENTE" else "ASSISTENTE IA",
            item.conteudo,
        )
        for item in data.mensagens
    ]

    started = perf_counter()
    try:
        context = build_simulator_ai_context(
            db,
            empresa_id=empresa.id,
            customer_name=data.perfil.nome,
            transcript=transcript,
            vehicle_type=data.perfil.tipo_veiculo,
            vehicle_description=data.perfil.veiculo,
            customer_notes=data.perfil.observacoes,
        )
        provider_response = request_openai(context)
    except AIConversationStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except AINotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except AIProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    latency_ms = max(1, round((perf_counter() - started) * 1000))
    session_hash = sha256(data.session_id.encode("utf-8")).hexdigest()[:16]

    db.add(
        Log(
            empresa_id=empresa.id,
            ator_tipo=AtorLog.IA,
            ator_id=None,
            acao="SIMULOU_RESPOSTA_IA",
            entidade="simulador_ia",
            entidade_id=None,
            detalhes={
                "session_hash": session_hash,
                "modelo": provider_response.model,
                "openai_response_id": provider_response.response_id,
                "latency_ms": latency_ms,
                "canal": "WHATSAPP_SIMULADO",
            },
        )
    )
    try:
        db.commit()
    except Exception:
        # A resposta ao cliente não deve falhar por um problema secundário de auditoria.
        db.rollback()

    return SimulatorReplyOut(
        id_whatsapp=f"wamid.sim.{uuid4().hex}",
        conteudo=provider_response.text,
        created_at=datetime.now(timezone.utc),
        model=provider_response.model,
        latency_ms=latency_ms,
    )
