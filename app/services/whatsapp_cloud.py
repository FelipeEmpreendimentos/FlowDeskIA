from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import TipoIntegracao
from app.models.models import Integracao
from app.services.ai_guided_flow import QuickReply


class WhatsAppCloudError(RuntimeError):
    pass


def _graph_url(path: str) -> str:
    return f"https://graph.facebook.com/{settings.meta_graph_version}/{path.lstrip('/')}"


def _graph_request(
    path: str,
    *,
    method: str = "GET",
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = _graph_url(path)
    if params:
        url = f"{url}?{urlencode({k: v for k, v in params.items() if v is not None})}"

    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=25) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
            message = data.get("error", {}).get("message") or raw
        except json.JSONDecodeError:
            message = raw or str(exc)
        raise WhatsAppCloudError(f"Meta WhatsApp API: {message}") from exc
    except URLError as exc:
        raise WhatsAppCloudError(
            "Não foi possível conectar aos servidores da Meta."
        ) from exc

    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WhatsAppCloudError("A Meta retornou uma resposta inválida.") from exc


def exchange_embedded_signup_code(code: str) -> str:
    if not settings.meta_app_id or not settings.meta_app_secret:
        raise WhatsAppCloudError(
            "A integração da Meta ainda não foi configurada no servidor."
        )
    data = _graph_request(
        "oauth/access_token",
        params={
            "client_id": settings.meta_app_id,
            "client_secret": settings.meta_app_secret,
            "code": code,
        },
    )
    token = str(data.get("access_token") or "").strip()
    if not token:
        raise WhatsAppCloudError("A Meta não retornou um token de acesso válido.")
    return token


def fetch_phone_profile(phone_number_id: str, token: str) -> dict[str, Any]:
    return _graph_request(
        phone_number_id,
        token=token,
        params={
            "fields": "display_phone_number,verified_name,quality_rating",
        },
    )


def subscribe_waba(waba_id: str, token: str) -> None:
    _graph_request(f"{waba_id}/subscribed_apps", method="POST", token=token, payload={})


def unsubscribe_waba(waba_id: str, token: str) -> None:
    _graph_request(f"{waba_id}/subscribed_apps", method="DELETE", token=token)


def active_company_integration(db: Session, empresa_id: int) -> Integracao | None:
    return db.scalar(
        select(Integracao)
        .where(
            Integracao.empresa_id == empresa_id,
            Integracao.tipo == TipoIntegracao.WHATSAPP,
            Integracao.ativo.is_(True),
        )
        .order_by(Integracao.updated_at.desc(), Integracao.id.desc())
        .limit(1)
    )


def integration_by_phone_number_id(db: Session, phone_number_id: str) -> Integracao | None:
    return db.scalar(
        select(Integracao)
        .where(
            Integracao.tipo == TipoIntegracao.WHATSAPP,
            Integracao.ativo.is_(True),
            Integracao.identificador == phone_number_id,
        )
        .order_by(Integracao.updated_at.desc(), Integracao.id.desc())
        .limit(1)
    )


def _normalize_phone(value: str) -> str:
    return "".join(char for char in value if char.isdigit())


def _send_payload(integration: Integracao, to: str, payload: dict[str, Any]) -> str:
    config = integration.configuracoes or {}
    phone_number_id = str(config.get("phone_number_id") or integration.identificador or "")
    token = str(integration.token or "")
    if not phone_number_id or not token:
        raise WhatsAppCloudError("A conexão do WhatsApp está incompleta.")

    message_payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": _normalize_phone(to),
        **payload,
    }
    data = _graph_request(
        f"{phone_number_id}/messages",
        method="POST",
        token=token,
        payload=message_payload,
    )
    messages = data.get("messages") or []
    message_id = str(messages[0].get("id") or "") if messages else ""
    if not message_id:
        raise WhatsAppCloudError("A Meta não confirmou o envio da mensagem.")
    return message_id


def send_text(integration: Integracao, *, to: str, text: str) -> str:
    return _send_payload(
        integration,
        to,
        payload={"type": "text", "text": {"preview_url": False, "body": text}},
    )


def _button_payload(text: str, options: list[QuickReply]) -> dict[str, Any]:
    return {
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text},
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {"id": option.id[:256], "title": option.label[:20]},
                    }
                    for option in options[:3]
                ]
            },
        },
    }


def _list_payload(text: str, options: list[QuickReply]) -> dict[str, Any]:
    return {
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": text},
            "action": {
                "button": "Escolher",
                "sections": [
                    {
                        "title": "Opções",
                        "rows": [
                            {
                                "id": option.id[:200],
                                "title": option.label[:24],
                            }
                            for option in options[:10]
                        ],
                    }
                ],
            },
        },
    }


def send_guided_message(
    integration: Integracao,
    *,
    to: str,
    text: str,
    options: Iterable[QuickReply] = (),
) -> str:
    quick_options = list(options)
    if not quick_options:
        return send_text(integration, to=to, text=text)
    payload = (
        _button_payload(text, quick_options)
        if len(quick_options) <= 3
        else _list_payload(text, quick_options)
    )
    return _send_payload(integration, to=to, payload=payload)


def send_text_if_connected(
    db: Session,
    *,
    empresa_id: int,
    to: str,
    text: str,
) -> str | None:
    integration = active_company_integration(db, empresa_id)
    if integration is None:
        return None
    return send_text(integration, to=to, text=text)


def verify_webhook_signature(raw_body: bytes, signature_header: str | None) -> bool:
    if not settings.meta_app_secret or not signature_header:
        return False
    prefix = "sha256="
    if not signature_header.startswith(prefix):
        return False
    expected = hmac.new(
        settings.meta_app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    received = signature_header[len(prefix) :]
    return hmac.compare_digest(expected, received)
