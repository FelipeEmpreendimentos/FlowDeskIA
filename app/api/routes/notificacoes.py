from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.database import get_db
from app.models.models import Notificacao, Usuario
from app.schemas.common import MessageResponse
from app.schemas.entities import NotificacaoOut
from app.services.db_utils import commit_or_conflict

router = APIRouter(prefix="/notificacoes", tags=["Notificações"])


@router.get("", response_model=list[NotificacaoOut])
def listar_notificacoes(
    somente_nao_lidas: bool = False,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Notificacao]:
    query = select(Notificacao).where(
        Notificacao.empresa_id == current_user.empresa_id,
        or_(
            Notificacao.usuario_id.is_(None),
            Notificacao.usuario_id == current_user.id,
        ),
    )
    if somente_nao_lidas:
        query = query.where(Notificacao.lida.is_(False))
    return list(db.scalars(query.order_by(Notificacao.created_at.desc())))


@router.patch("/{notificacao_id}/lida", response_model=NotificacaoOut)
def marcar_lida(
    notificacao_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Notificacao:
    item = db.scalar(
        select(Notificacao).where(
            Notificacao.id == notificacao_id,
            Notificacao.empresa_id == current_user.empresa_id,
            or_(
                Notificacao.usuario_id.is_(None),
                Notificacao.usuario_id == current_user.id,
            ),
        )
    )
    if item is None:
        raise HTTPException(404, "Notificação não encontrada.")
    item.lida = True
    return commit_or_conflict(db, item)


@router.patch("/marcar-todas-lidas", response_model=MessageResponse)
def marcar_todas_lidas(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    db.execute(
        update(Notificacao)
        .where(
            Notificacao.empresa_id == current_user.empresa_id,
            or_(
                Notificacao.usuario_id.is_(None),
                Notificacao.usuario_id == current_user.id,
            ),
        )
        .values(lida=True)
    )
    commit_or_conflict(db)
    return MessageResponse(mensagem="Notificações marcadas como lidas.")
