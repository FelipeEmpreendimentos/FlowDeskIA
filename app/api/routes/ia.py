from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.permissions import is_management
from app.database.database import get_db
from app.models.enums import StatusConversa
from app.models.models import Conversa, Mensagem, Usuario
from app.schemas.entities import MensagemOut
from app.services.ai_conversation import (
    AIConversationStateError,
    AINotConfiguredError,
    AIProviderError,
    generate_ai_reply,
)
from app.services.db_utils import commit_or_conflict

router = APIRouter(prefix="/ia", tags=["IA"])


def _get_conversation_for_update(
    db: Session,
    *,
    empresa_id: int,
    conversa_id: int,
) -> Conversa:
    item = db.scalar(
        select(Conversa)
        .where(
            Conversa.id == conversa_id,
            Conversa.empresa_id == empresa_id,
        )
        .with_for_update()
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversa não encontrada.")
    return item


def _ensure_conversation_access(item: Conversa, current_user: Usuario) -> None:
    if is_management(current_user):
        return
    if item.responsavel_id == current_user.id:
        return
    if item.responsavel_id is None and item.status == StatusConversa.ABERTA:
        return
    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        "Você só pode acessar conversas atribuídas a você ou ainda sem responsável.",
    )


@router.post(
    "/conversas/{conversa_id}/responder",
    response_model=MensagemOut,
    status_code=status.HTTP_201_CREATED,
)
def responder_conversa_com_ia(
    conversa_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Mensagem:
    conversa = _get_conversation_for_update(
        db,
        empresa_id=current_user.empresa_id,
        conversa_id=conversa_id,
    )
    _ensure_conversation_access(conversa, current_user)

    if conversa.status == StatusConversa.FINALIZADA:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Reabra a conversa antes de solicitar uma resposta da IA.",
        )

    try:
        message = generate_ai_reply(db, conversa)
    except AIConversationStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except AINotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except AIProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    return commit_or_conflict(db, message)
