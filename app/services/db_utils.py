from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def apply_patch(instance: Any, data: dict[str, Any]) -> Any:
    for field, value in data.items():
        setattr(instance, field, value)
    return instance


def _deliver_pending_whatsapp_message(db: Session, instance: Any | None) -> None:
    """Envia mensagens de saída do canal WhatsApp antes do commit.

    Mantemos a entrega centralizada aqui para que respostas humanas e respostas da
    IA usem o mesmo caminho existente de persistência de Mensagem. Mensagens que
    já possuem ``id_whatsapp`` (webhook/fluxo guiado) e mensagens do cliente não
    são reenviadas.
    """
    if instance is None:
        return

    from app.models.enums import OrigemConversa, RemetenteMensagem
    from app.models.models import Cliente, Conversa, Mensagem

    if not isinstance(instance, Mensagem):
        return
    if instance.id_whatsapp:
        return
    if instance.remetente == RemetenteMensagem.CLIENTE:
        return

    conversation = db.get(Conversa, instance.conversa_id)
    if conversation is None or conversation.origem != OrigemConversa.WHATSAPP:
        return

    from app.services.whatsapp_cloud import (
        WhatsAppCloudError,
        active_company_integration,
        send_text,
    )

    integration = active_company_integration(db, conversation.empresa_id)
    if integration is None:
        # Mantém compatibilidade com empresas que ainda usam somente o simulador.
        return

    client = db.get(Cliente, conversation.cliente_id)
    if client is None or not client.whatsapp:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "O cliente desta conversa não possui um WhatsApp cadastrado.",
        )

    try:
        instance.id_whatsapp = send_text(
            integration,
            to=client.whatsapp,
            text=instance.conteudo,
        )
    except WhatsAppCloudError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc


def commit_or_conflict(
    db: Session,
    instance: Any | None = None,
    message: str = "Não foi possível salvar. Verifique dados duplicados ou relacionamentos.",
) -> Any | None:
    try:
        _deliver_pending_whatsapp_message(db, instance)
        db.commit()
        if instance is not None:
            db.refresh(instance)
        return instance
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=message,
        ) from exc
