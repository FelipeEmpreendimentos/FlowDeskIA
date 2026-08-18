from __future__ import annotations

import re
from collections import defaultdict, deque
from datetime import datetime, timezone
from hashlib import sha256
from time import monotonic, perf_counter
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.super_admin_deps import get_current_super_admin
from app.database.database import get_db
from app.models.ai import AICompanySettings, AIContactMetadata
from app.models.models import Cliente, ConfigIA, Empresa, Veiculo
from app.models.platform import SuperAdmin, SuperAdminLog
from app.services.ai_agent import AIAgentError, AIAgentNotConfigured, AIAgentProviderError, reset_agent_session
from app.services.ai_guided_flow import run_guided_agent

router = APIRouter(
    prefix="/super-admin/simulador-ia",
    tags=["Super Admin - Simulador IA"],
)

RATE_WINDOW_SECONDS = 10 * 60
RATE_MAX_MESSAGES = 80
_rate_buckets: dict[str, deque[float]] = defaultdict(deque)


class SimulatorClientOut(BaseModel):
    id: int
    nome: str
    whatsapp: str | None
    telefone: str | None
    status: str
    criado_por_ia: bool = False
    cadastro_completo: bool = True


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
    veiculos: list[SimulatorVehicleOut]
    canal: str = "WHATSAPP_SIMULADO"
    novo_contato: bool = False
    criado_por_ia: bool = False
    cadastro_completo: bool = True


class NewContactRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=100)
    whatsapp: str | None = Field(default=None, max_length=30)


class ResetSessionRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=100)


class SimulatorHistoryMessage(BaseModel):
    remetente: Literal["CLIENTE", "IA"]
    conteudo: str = Field(min_length=1, max_length=1800)


class ToolTraceOut(BaseModel):
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]


class QuickReplyOut(BaseModel):
    id: str
    label: str
    kind: str = "default"


class SimulatorReplyRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=100)
    mensagens: list[SimulatorHistoryMessage] = Field(min_length=1, max_length=20)
    action_id: str | None = Field(default=None, max_length=160)


class SimulatorReplyOut(BaseModel):
    id_whatsapp: str
    remetente: Literal["IA"] = "IA"
    conteudo: str
    created_at: datetime
    model: str
    latency_ms: int
    status: Literal["ENTREGUE"] = "ENTREGUE"
    intent: str | None
    interpreted_as: str | None
    agent_state: str
    handoff: bool
    handoff_reason: str | None
    customer_id: int | None
    customer_complete: bool
    pending_action: dict[str, Any] | None
    quick_replies: list[QuickReplyOut]
    tools: list[ToolTraceOut]


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


def _metadata(db: Session, cliente_id: int) -> AIContactMetadata | None:
    return db.scalar(
        select(AIContactMetadata).where(AIContactMetadata.cliente_id == cliente_id)
    )


def _enforce_rate_limit(
    *,
    super_admin_id: int,
    empresa_id: int,
    customer_key: str,
) -> None:
    key = f"{super_admin_id}:{empresa_id}:{customer_key}"
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


def _normalize_phone(value: str | None) -> str:
    digits = re.sub(r"\D", "", value or "")
    if not digits:
        suffix = str(uuid4().int)[-9:]
        return "55" + "9" + suffix
    if len(digits) < 10 or len(digits) > 13:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Informe um telefone/WhatsApp válido com DDD.",
        )
    if len(digits) in {10, 11}:
        digits = "55" + digits
    return digits


def _bootstrap(db: Session, empresa: Empresa, cliente: Cliente) -> SimulatorBootstrapOut:
    config = db.scalar(select(ConfigIA).where(ConfigIA.empresa_id == empresa.id))
    metadata = _metadata(db, cliente.id)
    vehicles = list(
        db.scalars(
            select(Veiculo)
            .where(Veiculo.cliente_id == cliente.id)
            .order_by(Veiculo.created_at.desc())
            .limit(12)
        )
    )
    assistant = (
        config.nome_assistente.strip()
        if config and config.nome_assistente and config.nome_assistente.strip()
        else "Assistente"
    )
    return SimulatorBootstrapOut(
        empresa_id=empresa.id,
        empresa=empresa.nome,
        cliente_id=cliente.id,
        cliente=cliente.nome,
        cliente_whatsapp=cliente.whatsapp or cliente.telefone,
        assistente=assistant,
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
            for item in vehicles
        ],
        novo_contato=bool(metadata and not metadata.cadastro_completo),
        criado_por_ia=bool(metadata and metadata.criado_por_ia),
        cadastro_completo=metadata.cadastro_completo if metadata else True,
    )


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
    term = (busca or "").strip().lower()
    if term:
        like = f"%{term}%"
        query = query.where(
            or_(
                func.lower(Cliente.nome).like(like),
                func.lower(func.coalesce(Cliente.whatsapp, "")).like(like),
                func.lower(func.coalesce(Cliente.telefone, "")).like(like),
            )
        )

    clients = list(db.scalars(query.order_by(Cliente.nome).limit(limit)))
    metadata_rows = {
        item.cliente_id: item
        for item in db.scalars(
            select(AIContactMetadata).where(
                AIContactMetadata.empresa_id == empresa_id,
                AIContactMetadata.cliente_id.in_([client.id for client in clients] or [-1]),
            )
        )
    }
    return [
        SimulatorClientOut(
            id=item.id,
            nome=item.nome,
            whatsapp=item.whatsapp,
            telefone=item.telefone,
            status=item.status.value,
            criado_por_ia=bool(
                metadata_rows.get(item.id) and metadata_rows[item.id].criado_por_ia
            ),
            cadastro_completo=(
                metadata_rows[item.id].cadastro_completo
                if item.id in metadata_rows
                else True
            ),
        )
        for item in clients
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
    return _bootstrap(db, empresa, cliente)


@router.post(
    "/empresas/{empresa_id}/novo-contato",
    response_model=SimulatorBootstrapOut,
    status_code=status.HTTP_201_CREATED,
)
def criar_novo_contato_simulado(
    empresa_id: int,
    data: NewContactRequest,
    current: SuperAdmin = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
) -> SimulatorBootstrapOut:
    del current
    empresa = _require_company(db, empresa_id)
    company_settings = db.scalar(
        select(AICompanySettings).where(AICompanySettings.empresa_id == empresa_id)
    )
    if company_settings is not None and not company_settings.criar_cliente_auto:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A criação automática de clientes está desativada na configuração desta empresa.",
        )

    phone = _normalize_phone(data.whatsapp)
    existing = db.scalar(
        select(Cliente).where(
            Cliente.empresa_id == empresa_id,
            or_(
                func.regexp_replace(func.coalesce(Cliente.whatsapp, ""), r"\D", "", "g")
                == phone,
                func.regexp_replace(func.coalesce(Cliente.telefone, ""), r"\D", "", "g")
                == phone,
            ),
        )
    )
    if existing is not None:
        reset_agent_session(
            db,
            empresa_id=empresa_id,
            external_id=data.session_id,
            cliente_id=existing.id,
        )
        return _bootstrap(db, empresa, existing)

    cliente = Cliente(
        empresa_id=empresa_id,
        nome=f"Contato WhatsApp {phone[-4:]}",
        telefone=None,
        whatsapp=phone,
        email=None,
        cpf=None,
        data_nascimento=None,
        observacoes=None,
    )
    db.add(cliente)
    db.flush()
    db.add(
        AIContactMetadata(
            cliente_id=cliente.id,
            empresa_id=empresa_id,
            criado_por_ia=True,
            origem="SIMULADOR_IA",
            cadastro_completo=False,
        )
    )
    db.commit()
    reset_agent_session(
        db,
        empresa_id=empresa_id,
        external_id=data.session_id,
        cliente_id=cliente.id,
    )
    return _bootstrap(db, empresa, cliente)


@router.post(
    "/empresas/{empresa_id}/clientes/{cliente_id}/reset",
    response_model=SimulatorBootstrapOut,
)
def resetar_simulacao(
    empresa_id: int,
    cliente_id: int,
    data: ResetSessionRequest,
    current: SuperAdmin = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
) -> SimulatorBootstrapOut:
    del current
    empresa = _require_company(db, empresa_id)
    cliente = _require_client(db, empresa_id, cliente_id)
    reset_agent_session(
        db,
        empresa_id=empresa_id,
        external_id=data.session_id,
        cliente_id=cliente_id,
    )
    return _bootstrap(db, empresa, cliente)


@router.delete(
    "/empresas/{empresa_id}/clientes/{cliente_id}/contato-teste",
    status_code=status.HTTP_204_NO_CONTENT,
)
def excluir_contato_de_teste(
    empresa_id: int,
    cliente_id: int,
    current: SuperAdmin = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
) -> Response:
    del current
    cliente = _require_client(db, empresa_id, cliente_id)
    metadata = _metadata(db, cliente_id)
    if (
        metadata is None
        or not metadata.criado_por_ia
        or metadata.origem != "SIMULADOR_IA"
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Somente contatos criados pelo laboratório podem ser removidos por esta ação.",
        )
    db.delete(cliente)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
        customer_key=f"{cliente_id}:{data.session_id}",
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
        result = run_guided_agent(
            db,
            empresa_id=empresa_id,
            cliente_id=cliente_id,
            session_id=data.session_id,
            transcript=transcript,
            action_id=data.action_id,
        )
    except AIAgentNotConfigured as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except AIAgentProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    except (AIAgentError, RuntimeError, ValueError) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    latency_ms = max(1, round((perf_counter() - started) * 1000))
    session_hash = sha256(data.session_id.encode("utf-8")).hexdigest()[:16]
    trace = [
        {
            "name": item.name,
            "arguments": item.arguments,
            "result": item.result,
        }
        for item in result.tool_trace
    ]
    db.add(
        SuperAdminLog(
            super_admin_id=current.id,
            empresa_id=empresa_id,
            acao="SIMULOU_FLUXO_GUIADO_IA",
            entidade="clientes",
            entidade_id=cliente_id,
            dados_anteriores=None,
            dados_novos={
                "session_hash": session_hash,
                "modelo": result.model,
                "openai_response_id": result.response_id,
                "latency_ms": latency_ms,
                "canal": "WHATSAPP_SIMULADO",
                "intent": result.intent,
                "interpreted_as": result.interpreted_as,
                "state": result.state,
                "handoff": result.handoff,
                "action_id": data.action_id,
                "quick_replies": [item.id for item in result.options],
                "tools": trace[-12:],
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
        conteudo=result.text,
        created_at=datetime.now(timezone.utc),
        model=result.model,
        latency_ms=latency_ms,
        intent=result.intent,
        interpreted_as=result.interpreted_as,
        agent_state=result.state,
        handoff=result.handoff,
        handoff_reason=result.handoff_reason,
        customer_id=result.customer_id,
        customer_complete=result.customer_complete,
        pending_action=result.pending_action,
        quick_replies=[
            QuickReplyOut(id=item.id, label=item.label, kind=item.kind)
            for item in result.options
        ],
        tools=[
            ToolTraceOut(
                name=item.name,
                arguments=item.arguments,
                result=item.result,
            )
            for item in result.tool_trace
        ],
    )
