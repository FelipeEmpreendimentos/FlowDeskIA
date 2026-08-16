from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from hashlib import sha256
from time import monotonic, perf_counter
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.super_admin_deps import get_current_super_admin
from app.database.database import get_db
from app.models.models import Cliente, ConfigIA, Empresa, Veiculo
from app.models.platform import SuperAdmin, SuperAdminLog
from app.services.ai_conversation import (
    AIConversationStateError,
    AINotConfiguredError,
    AIProviderError,
    request_openai,
)
from app.services.ai_simulator import build_real_customer_simulator_context

router = APIRouter(
    prefix="/super-admin/simulador-ia",
    tags=["Super Admin - Simulador IA"],
)

RATE_WINDOW_SECONDS = 10 * 60
RATE_MAX_MESSAGES = 60
_rate_buckets: dict[str, deque[float]] = defaultdict(deque)


class SimulatorClientOut(BaseModel):
    id: int
    nome: str
    whatsapp: str | None
    telefone: str | None
    status: str


class SimulatorVehicleOut(BaseModel):
    id: int
    tipo_veiculo: str | None
    marca: str | None
    modelo: str | None
    ano: int | None
    cor: str | None
    apelido: str | None


class SimulatorBootstrapOut(BaseModel):
    empresa_id: int
    empresa: str
    cliente_id: int
    cliente: str
    cliente_whatsapp: str | None
    assistente: str
    mensagem_boas_vindas: str
    veiculos: list[SimulatorVehicleOut]
    canal: str = "WHATSAPP_SIMULADO"


class SimulatorHistoryMessage(BaseModel):
    remetente: Literal["CLIENTE", "IA"]
    conteudo: str = Field(min_length=1, max_length=1600)


class SimulatorReplyRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=100)
    mensagens: list[SimulatorHistoryMessage] = Field(min_length=1, max_length=20)


class SimulatorReplyOut(BaseModel):
    id_whatsapp: str
    remetente: Literal["IA"] = "IA"
    conteudo: str
    created_at: datetime
    model: str
    latency_ms: int
    status: Literal["ENTREGUE"] = "ENTREGUE"


def _ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _require_company(db: Session, empresa_id: int) -> Empresa:
    empresa = db.scalar(select(Empresa).where(Empresa.id == empresa_id))
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa não encontrada.")
    return empresa


def _require_client(db: Session, empresa_id: int, cliente_id: int) -> Cliente:
    cliente = db.scalar(
        select(Cliente).where(
            Cliente.id == cliente_id,
            Cliente.empresa_id == empresa_id,
        )
    )
    if cliente is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Cliente não encontrado nesta empresa.",
        )
    return cliente


def _enforce_rate_limit(
    *,
    super_admin_id: int,
    empresa_id: int,
    cliente_id: int,
) -> None:
    key = f"{super_admin_id}:{empresa_id}:{cliente_id}"
    now = monotonic()
    bucket = _rate_buckets[key]
    while bucket and now - bucket[0] > RATE_WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= RATE_MAX_MESSAGES:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Limite do laboratório atingido. Aguarde alguns minutos antes de continuar.",
        )
    bucket.append(now)


@router.get(
    "/empresas/{empresa_id}/clientes",
    response_model=list[SimulatorClientOut],
)
def listar_clientes_para_simulacao(
    empresa_id: int,
    busca: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=100, ge=1, le=250),
    current: SuperAdmin = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
) -> list[SimulatorClientOut]:
    del current
    _require_company(db, empresa_id)

    query = select(Cliente).where(Cliente.empresa_id == empresa_id)
    termo = (busca or "").strip().lower()
    if termo:
        like = f"%{termo}%"
        query = query.where(
            or_(
                func.lower(Cliente.nome).like(like),
                func.lower(func.coalesce(Cliente.whatsapp, "")).like(like),
                func.lower(func.coalesce(Cliente.telefone, "")).like(like),
            )
        )

    clientes = list(db.scalars(query.order_by(Cliente.nome).limit(limit)))
    return [
        SimulatorClientOut(
            id=item.id,
            nome=item.nome,
            whatsapp=item.whatsapp,
            telefone=item.telefone,
            status=item.status.value,
        )
        for item in clientes
    ]


@router.get(
    "/empresas/{empresa_id}/clientes/{cliente_id}",
    response_model=SimulatorBootstrapOut,
)
def preparar_simulacao(
    empresa_id: int,
    cliente_id: int,
    current: SuperAdmin = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
) -> SimulatorBootstrapOut:
    del current
    empresa = _require_company(db, empresa_id)
    cliente = _require_client(db, empresa_id, cliente_id)
    config = db.scalar(select(ConfigIA).where(ConfigIA.empresa_id == empresa_id))
    veiculos = list(
        db.scalars(
            select(Veiculo)
            .where(Veiculo.cliente_id == cliente_id)
            .order_by(Veiculo.created_at.desc())
            .limit(12)
        )
    )

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
        else f"Olá, {cliente.nome}! 👋 Como posso ajudar?"
    )

    return SimulatorBootstrapOut(
        empresa_id=empresa.id,
        empresa=empresa.nome,
        cliente_id=cliente.id,
        cliente=cliente.nome,
        cliente_whatsapp=cliente.whatsapp or cliente.telefone,
        assistente=assistente,
        mensagem_boas_vindas=boas_vindas,
        veiculos=[
            SimulatorVehicleOut(
                id=item.id,
                tipo_veiculo=item.tipo_veiculo,
                marca=item.marca,
                modelo=item.modelo,
                ano=item.ano,
                cor=item.cor,
                apelido=item.apelido,
            )
            for item in veiculos
        ],
    )


@router.post(
    "/empresas/{empresa_id}/clientes/{cliente_id}/responder",
    response_model=SimulatorReplyOut,
)
def responder_no_simulador(
    empresa_id: int,
    cliente_id: int,
    data: SimulatorReplyRequest,
    request: Request,
    current: SuperAdmin = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
) -> SimulatorReplyOut:
    _require_company(db, empresa_id)
    _require_client(db, empresa_id, cliente_id)
    _enforce_rate_limit(
        super_admin_id=current.id,
        empresa_id=empresa_id,
        cliente_id=cliente_id,
    )

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
        context = build_real_customer_simulator_context(
            db,
            empresa_id=empresa_id,
            cliente_id=cliente_id,
            transcript=transcript,
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
        SuperAdminLog(
            super_admin_id=current.id,
            empresa_id=empresa_id,
            acao="SIMULOU_RESPOSTA_IA",
            entidade="clientes",
            entidade_id=cliente_id,
            dados_anteriores=None,
            dados_novos={
                "session_hash": session_hash,
                "modelo": provider_response.model,
                "openai_response_id": provider_response.response_id,
                "latency_ms": latency_ms,
                "canal": "WHATSAPP_SIMULADO",
            },
            ip=_ip(request),
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()

    return SimulatorReplyOut(
        id_whatsapp=f"wamid.sim.{uuid4().hex}",
        conteudo=provider_response.text,
        created_at=datetime.now(timezone.utc),
        model=provider_response.model,
        latency_ms=latency_ms,
    )
