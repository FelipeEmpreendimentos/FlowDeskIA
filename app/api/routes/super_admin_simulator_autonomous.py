from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.super_admin_simulator import (
    QuickReplyOut,
    SimulatorReplyOut,
    SimulatorReplyRequest,
    ToolTraceOut,
    _enforce_rate_limit,
    _ip,
    _require_client,
    _require_company,
)
from app.api.super_admin_deps import get_current_super_admin
from app.database.database import get_db
from app.models.enums import (
    OrigemConversa,
    RemetenteMensagem,
    StatusConversa,
    TipoMensagem,
)
from app.models.models import Conversa, Mensagem
from app.models.platform import SuperAdmin, SuperAdminLog
from app.services.ai_guided_customization import run_customized_guided_agent
from app.services.attendance_presence import distribute_handoff_conversation


router = APIRouter(
    prefix="/super-admin/simulador-ia",
    tags=["Super Admin - Simulador IA autônomo"],
)


def _mirror_conversation(
    db: Session,
    *,
    empresa_id: int,
    cliente_id: int,
    session_hash: str,
) -> Conversa:
    prefix = f"sim.{session_hash}."
    existing_id = db.scalar(
        select(Mensagem.conversa_id)
        .join(Conversa, Conversa.id == Mensagem.conversa_id)
        .where(
            Conversa.empresa_id == empresa_id,
            Conversa.cliente_id == cliente_id,
            Mensagem.id_whatsapp.like(prefix + "%"),
        )
        .order_by(Mensagem.id)
        .limit(1)
    )
    if existing_id:
        conversation = db.scalar(
            select(Conversa).where(
                Conversa.id == existing_id,
                Conversa.empresa_id == empresa_id,
            )
        )
        if conversation is not None:
            return conversation

    conversation = Conversa(
        empresa_id=empresa_id,
        cliente_id=cliente_id,
        responsavel_id=None,
        status=StatusConversa.ABERTA,
        origem=OrigemConversa.WHATSAPP,
        ia_ativa=True,
        ultima_mensagem_id=None,
        ultima_interacao=datetime.now(timezone.utc),
        finalizada_em=None,
        finalizada_por_id=None,
        resumo_finalizacao="[SIMULAÇÃO INTERNA DO SUPER ADMIN]",
        avaliacao_solicitada=False,
        avaliacao_token=None,
        avaliacao_enviada_em=None,
        avaliacao_nota=None,
        avaliacao_comentario=None,
        avaliacao_respondida_em=None,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def _persist_mirror_message(
    db: Session,
    *,
    conversation: Conversa,
    id_whatsapp: str,
    sender: RemetenteMensagem,
    content: str,
) -> Mensagem:
    existing = db.scalar(
        select(Mensagem).where(Mensagem.id_whatsapp == id_whatsapp)
    )
    if existing is not None:
        return existing

    now = datetime.now(timezone.utc)
    message = Mensagem(
        conversa_id=conversation.id,
        remetente=sender,
        conteudo=content,
        tipo=TipoMensagem.TEXTO,
        arquivo_url=None,
        id_whatsapp=id_whatsapp,
        lida=sender != RemetenteMensagem.CLIENTE,
        data_envio=now,
    )
    db.add(message)
    db.flush()
    conversation.ultima_mensagem_id = message.id
    conversation.ultima_interacao = now
    if sender == RemetenteMensagem.IA:
        conversation.ia_ativa = True
    db.commit()
    return message


@router.post(
    "/empresas/{empresa_id}/clientes/{cliente_id}/responder-autonomo",
    response_model=SimulatorReplyOut,
)
def responder_no_simulador_autonomo(
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
        customer_key=f"autonomo:{cliente_id}:{data.session_id}",
    )

    if not data.mensagens or data.mensagens[-1].remetente != "CLIENTE":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A última mensagem do simulador precisa ser do cliente.",
        )

    session_hash = sha256(data.session_id.encode("utf-8")).hexdigest()[:16]
    conversation = _mirror_conversation(
        db,
        empresa_id=empresa_id,
        cliente_id=cliente_id,
        session_hash=session_hash,
    )
    client_message_number = len(data.mensagens)
    _persist_mirror_message(
        db,
        conversation=conversation,
        id_whatsapp=f"sim.{session_hash}.c.{client_message_number}",
        sender=RemetenteMensagem.CLIENTE,
        content=data.mensagens[-1].conteudo,
    )

    transcript = [
        (
            "CLIENTE" if item.remetente == "CLIENTE" else "ASSISTENTE IA",
            item.conteudo,
        )
        for item in data.mensagens
    ]

    started = perf_counter()
    result = run_customized_guided_agent(
        db,
        empresa_id=empresa_id,
        cliente_id=cliente_id,
        session_id=data.session_id,
        transcript=transcript,
        action_id=data.action_id,
    )
    latency_ms = max(1, round((perf_counter() - started) * 1000))

    assistant_external_id = f"sim.{session_hash}.a.{client_message_number + 1}"
    _persist_mirror_message(
        db,
        conversation=conversation,
        id_whatsapp=assistant_external_id,
        sender=RemetenteMensagem.IA,
        content=result.text,
    )

    distribution: dict[str, object] | None = None
    if result.handoff:
        distribution = distribute_handoff_conversation(
            db,
            conversation=conversation,
            reason=(
                result.handoff_reason
                or "Atendimento transferido pela IA para acompanhamento humano."
            ),
        )

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
            acao="SIMULOU_ATENDIMENTO_AUTONOMO_IA",
            entidade="conversas",
            entidade_id=conversation.id,
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
                "distribuicao": distribution,
                "action_id": data.action_id,
                "quick_replies": [item.id for item in result.options],
                "tools": trace[-12:],
                "conversa_espelhada_id": conversation.id,
            },
            ip=_ip(request),
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()

    return SimulatorReplyOut(
        id_whatsapp=assistant_external_id or f"wamid.sim.{uuid4().hex}",
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
