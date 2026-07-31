from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.database import get_db
from app.models.engagement import PreferenciaNotificacao
from app.models.models import Usuario
from app.schemas.engagement import (
    PreferenciaNotificacaoOut,
    PreferenciaNotificacaoUpdate,
)


router = APIRouter(
    prefix="/preferencias-notificacoes",
    tags=["Preferências de notificações"],
)


def _obter_ou_criar(
    db: Session,
    user: Usuario,
) -> PreferenciaNotificacao:
    preferencia = db.scalar(
        select(PreferenciaNotificacao).where(
            PreferenciaNotificacao.usuario_id == user.id,
            PreferenciaNotificacao.empresa_id == user.empresa_id,
        )
    )
    if preferencia is None:
        preferencia = PreferenciaNotificacao(
            empresa_id=user.empresa_id,
            usuario_id=user.id,
        )
        db.add(preferencia)
        db.flush()
    return preferencia


@router.get("", response_model=PreferenciaNotificacaoOut)
def obter_preferencias(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PreferenciaNotificacao:
    preferencia = _obter_ou_criar(db, current_user)
    db.commit()
    db.refresh(preferencia)
    return preferencia


@router.put("", response_model=PreferenciaNotificacaoOut)
def atualizar_preferencias(
    data: PreferenciaNotificacaoUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PreferenciaNotificacao:
    preferencia = _obter_ou_criar(db, current_user)
    for campo, valor in data.model_dump().items():
        setattr(preferencia, campo, valor)
    preferencia.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(preferencia)
    return preferencia
