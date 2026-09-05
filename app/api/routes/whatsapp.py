from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.database.database import get_db
from app.models.enums import (
    OrigemConversa,
    RemetenteMensagem,
    StatusConversa,
    TipoIntegracao,
    TipoMensagem,
)
from app.models.models import Cliente, Conversa, Integracao, Mensagem, Usuario
from app.schemas.whatsapp import (
    WhatsAppConnectRequest,
    WhatsAppConnectionTestOut,
    WhatsAppIntegrationOut,
)
from app.services.access_control import require_module_access, require_module_manage
from app.services.ai_guided_customization import run_customized_guided_agent
from app.services.attendance_presence import distribute_handoff_conversation
from app.services.audit import add_audit_log
from app.services.whatsapp_cloud import (
    WhatsAppCloudError,
    exchange_embedded_signup_code,
    fetch_phone_profile,
    integration_by_phone_number_id,
    send_guided_message,
    subscribe_waba,
    unsubscribe_waba,
    verify_webhook_signature,
)


router = APIRouter(tags=["WhatsApp"])


def _integration_out(item: Integracao | None) -> WhatsAppIntegrationOut:
    if item is None or not item.ativo:
        return WhatsAppIntegrationOut(connected=False)
    config = item.configuracoes or {}
    return WhatsAppIntegrationOut(
        connected=True,
        phone_number_id=str(config.get("phone_number_id") or item.identificador or "") or None,
        waba_id=str(config.get("waba_id") or "") or None,
        business_id=str(config.get("business_id") or "") or None,
        display_phone_number=str(config.get("display_phone_number") or "") or None,
        verified_name=str(config.get("verified_name") or "") or None,
        quality_rating=str(config.get("quality_rating") or "") or None,
        connection_mode=config.get("connection_mode") or "CLOUD_API",
        updated_at=item.updated_at,
    )


def _company_integration(db: Session, empresa_id: int) -> Integracao | None:
    return db.scalar(
        select(Integracao)
        .where(
            Integracao.empresa_id == empresa_id,
            Integracao.tipo == TipoIntegracao.WHATSAPP,
        )
        .order_by(Integracao.updated_at.desc(), Integracao.id.desc())
        .limit(1)
    )


def _require_connected(item: Integracao | None) -> Integracao:
    if item is None or not item.ativo or not item.token:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Nenhum WhatsApp está conectado a esta empresa.",
        )
    return item


@router.get("/whatsapp/integracao", response_model=WhatsAppIntegrationOut)
def whatsapp_integration_status(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WhatsAppIntegrationOut:
    require_module_access(db, current_user, "WHATSAPP")
    return _integration_out(_company_integration(db, current_user.empresa_id))


@router.post("/whatsapp/conectar", response_model=WhatsAppIntegrationOut)
def connect_whatsapp(
    data: WhatsAppConnectRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WhatsAppIntegrationOut:
    require_module_manage(db, current_user, "WHATSAPP")

    try:
        access_token = exchange_embedded_signup_code(data.code)
        profile = fetch_phone_profile(data.phone_number_id, access_token)
        subscribe_waba(data.waba_id, access_token)
    except WhatsAppCloudError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    now = datetime.now(timezone.utc)
    previous = list(
        db.scalars(
            select(Integracao).where(
                Integracao.empresa_id == current_user.empresa_id,
                Integracao.tipo == TipoIntegracao.WHATSAPP,
            )
        )
    )
    for item in previous:
        item.ativo = False
        item.updated_at = now

    integration = Integracao(
        empresa_id=current_user.empresa_id,
        tipo=TipoIntegracao.WHATSAPP,
        nome="WhatsApp Business Platform",
        ativo=True,
        identificador=data.phone_number_id,
        token=access_token,
        configuracoes={
            "provider": "META_CLOUD_API",
            "waba_id": data.waba_id,
            "phone_number_id": data.phone_number_id,
            "business_id": data.business_id,
            "connection_mode": data.connection_mode,
            "display_phone_number": profile.get("display_phone_number"),
            "verified_name": profile.get("verified_name"),
            "quality_rating": profile.get("quality_rating"),
        },
        updated_at=now,
    )
    db.add(integration)
    db.flush()
    add_audit_log(
        db,
        user=current_user,
        action="CONECTOU_WHATSAPP_META",
        entity="integracoes",
        entity_id=integration.id,
        details={
            "phone_number_id": data.phone_number_id,
            "waba_id": data.waba_id,
            "modo": data.connection_mode,
        },
    )
    db.commit()
    db.refresh(integration)
    return _integration_out(integration)


@router.post("/whatsapp/testar", response_model=WhatsAppConnectionTestOut)
def test_whatsapp_connection(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WhatsAppConnectionTestOut:
    require_module_manage(db, current_user, "WHATSAPP")
    integration = _require_connected(_company_integration(db, current_user.empresa_id))
    config = integration.configuracoes or {}
    phone_number_id = str(config.get("phone_number_id") or integration.identificador or "")
    try:
        profile = fetch_phone_profile(phone_number_id, str(integration.token))
    except WhatsAppCloudError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    config = {
        **config,
        "display_phone_number": profile.get("display_phone_number"),
        "verified_name": profile.get("verified_name"),
        "quality_rating": profile.get("quality_rating"),
    }
    integration.configuracoes = config
    integration.updated_at = datetime.now(timezone.utc)
    db.commit()
    return WhatsAppConnectionTestOut(
        ok=True,
        message="Conexão com a Meta validada com sucesso.",
        display_phone_number=profile.get("display_phone_number"),
        verified_name=profile.get("verified_name"),
        quality_rating=profile.get("quality_rating"),
    )


@router.post("/whatsapp/desconectar", response_model=WhatsAppIntegrationOut)
def disconnect_whatsapp(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WhatsAppIntegrationOut:
    require_module_manage(db, current_user, "WHATSAPP")
    integration = _require_connected(_company_integration(db, current_user.empresa_id))
    config = integration.configuracoes or {}
    waba_id = str(config.get("waba_id") or "")
    if waba_id:
        try:
            unsubscribe_waba(waba_id, str(integration.token))
        except WhatsAppCloudError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    integration.ativo = False
    integration.token = None
    integration.updated_at = datetime.now(timezone.utc)
    add_audit_log(
        db,
        user=current_user,
        action="DESCONECTOU_WHATSAPP_META",
        entity="integracoes",
        entity_id=integration.id,
    )
    db.commit()
    db.refresh(integration)
    return WhatsAppIntegrationOut(connected=False)


def _normalize_phone(value: str | None) -> str:
    return "".join(char for char in (value or "") if char.isdigit())


def _find_or_create_client(
    db: Session,
    *,
    empresa_id: int,
    whatsapp_number: str,
    contact_name: str | None,
) -> Cliente:
    digits = _normalize_phone(whatsapp_number)
    candidates = list(
        db.scalars(
            select(Cliente).where(
                Cliente.empresa_id == empresa_id,
                Cliente.whatsapp.is_not(None),
            )
        )
    )
    for client in candidates:
        if _normalize_phone(client.whatsapp) == digits:
            return client

    client = Cliente(
        empresa_id=empresa_id,
        nome=(contact_name or f"WhatsApp {digits[-4:]}").strip(),
        whatsapp=f"+{digits}",
    )
    db.add(client)
    db.flush()
    return client


def _active_conversation(db: Session, empresa_id: int, cliente_id: int) -> Conversa | None:
    return db.scalar(
        select(Conversa)
        .where(
            Conversa.empresa_id == empresa_id,
            Conversa.cliente_id == cliente_id,
            Conversa.origem == OrigemConversa.WHATSAPP,
            Conversa.status.in_([StatusConversa.ABERTA, StatusConversa.EM_ATENDIMENTO]),
        )
        .order_by(Conversa.ultima_interacao.desc().nullslast(), Conversa.id.desc())
        .limit(1)
    )


def _message_content(message: dict[str, Any]) -> tuple[str, str | None, bool]:
    message_type = str(message.get("type") or "")
    if message_type == "text":
        return str((message.get("text") or {}).get("body") or "").strip(), None, True
    if message_type == "interactive":
        interactive = message.get("interactive") or {}
        reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
        return str(reply.get("title") or "").strip(), str(reply.get("id") or "") or None, True
    if message_type == "button":
        button = message.get("button") or {}
        return str(button.get("text") or "").strip(), str(button.get("payload") or "") or None, True
    labels = {
        "image": "[Imagem recebida pelo WhatsApp]",
        "audio": "[Áudio recebido pelo WhatsApp]",
        "document": "[Documento recebido pelo WhatsApp]",
        "video": "[Vídeo recebido pelo WhatsApp]",
        "location": "[Localização recebida pelo WhatsApp]",
        "contacts": "[Contato recebido pelo WhatsApp]",
        "sticker": "[Figurinha recebida pelo WhatsApp]",
    }
    return labels.get(message_type, "[Mensagem recebida pelo WhatsApp]"), None, False


def _transcript(db: Session, conversation_id: int) -> list[tuple[str, str]]:
    messages = list(
        db.scalars(
            select(Mensagem)
            .where(Mensagem.conversa_id == conversation_id)
            .order_by(Mensagem.data_envio.desc(), Mensagem.id.desc())
            .limit(40)
        )
    )
    messages.reverse()
    return [
        (
            "CLIENTE" if message.remetente == RemetenteMensagem.CLIENTE else "ASSISTENTE IA",
            message.conteudo,
        )
        for message in messages
    ]


def _process_inbound_message(
    db: Session,
    *,
    integration: Integracao,
    message: dict[str, Any],
    contacts: list[dict[str, Any]],
) -> None:
    external_id = str(message.get("id") or "")
    if not external_id or db.scalar(select(Mensagem.id).where(Mensagem.id_whatsapp == external_id)):
        return

    sender = str(message.get("from") or "")
    if not sender:
        return
    profile_name = None
    if contacts:
        profile_name = str((contacts[0].get("profile") or {}).get("name") or "") or None

    client = _find_or_create_client(
        db,
        empresa_id=integration.empresa_id,
        whatsapp_number=sender,
        contact_name=profile_name,
    )
    conversation = _active_conversation(db, integration.empresa_id, client.id)
    if conversation is None:
        conversation = Conversa(
            empresa_id=integration.empresa_id,
            cliente_id=client.id,
            responsavel_id=None,
            status=StatusConversa.ABERTA,
            origem=OrigemConversa.WHATSAPP,
            ia_ativa=True,
            ultima_interacao=datetime.now(timezone.utc),
        )
        db.add(conversation)
        db.flush()

    content, action_id, process_with_ai = _message_content(message)
    now = datetime.now(timezone.utc)
    inbound = Mensagem(
        conversa_id=conversation.id,
        remetente=RemetenteMensagem.CLIENTE,
        conteudo=content or "[Mensagem vazia recebida pelo WhatsApp]",
        tipo=TipoMensagem.TEXTO,
        arquivo_url=None,
        id_whatsapp=external_id,
        lida=False,
        data_envio=now,
    )
    db.add(inbound)
    db.flush()
    conversation.ultima_mensagem_id = inbound.id
    conversation.ultima_interacao = now
    db.commit()
    db.refresh(conversation)

    if not conversation.ia_ativa or not process_with_ai:
        return

    config = integration.configuracoes or {}
    phone_number_id = str(config.get("phone_number_id") or integration.identificador or "")
    result = run_customized_guided_agent(
        db,
        empresa_id=integration.empresa_id,
        cliente_id=client.id,
        session_id=f"wa:{phone_number_id}:{sender}",
        transcript=_transcript(db, conversation.id),
        action_id=action_id,
        canal="WHATSAPP",
    )

    if result.handoff:
        distribute_handoff_conversation(
            db,
            conversation=conversation,
            reason=result.handoff_reason or "Atendimento transferido pela IA.",
        )

    try:
        outbound_id = send_guided_message(
            integration,
            to=sender,
            text=result.text,
            options=result.options,
        )
    except WhatsAppCloudError:
        return

    assistant_message = Mensagem(
        conversa_id=conversation.id,
        remetente=RemetenteMensagem.IA,
        conteudo=result.text,
        tipo=TipoMensagem.TEXTO,
        arquivo_url=None,
        id_whatsapp=outbound_id,
        lida=True,
        data_envio=datetime.now(timezone.utc),
    )
    db.add(assistant_message)
    db.flush()
    conversation.ultima_mensagem_id = assistant_message.id
    conversation.ultima_interacao = assistant_message.data_envio
    db.commit()


@router.get("/webhooks/whatsapp/meta")
def verify_meta_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> Response:
    if (
        hub_mode == "subscribe"
        and settings.meta_whatsapp_verify_token
        and hub_verify_token == settings.meta_whatsapp_verify_token
        and hub_challenge is not None
    ):
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Webhook da Meta não autorizado.")


@router.post("/webhooks/whatsapp/meta", status_code=status.HTTP_200_OK)
async def receive_meta_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    raw = await request.body()
    if not verify_webhook_signature(raw, request.headers.get("x-hub-signature-256")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Assinatura do webhook inválida.")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Webhook inválido.") from exc

    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            if change.get("field") != "messages":
                continue
            value = change.get("value") or {}
            metadata = value.get("metadata") or {}
            phone_number_id = str(metadata.get("phone_number_id") or "")
            if not phone_number_id:
                continue
            integration = integration_by_phone_number_id(db, phone_number_id)
            if integration is None:
                continue
            contacts = value.get("contacts") or []
            for message in value.get("messages") or []:
                _process_inbound_message(
                    db,
                    integration=integration,
                    message=message,
                    contacts=contacts,
                )

    return {"ok": True}
