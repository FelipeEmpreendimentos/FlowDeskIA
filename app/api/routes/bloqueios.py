from datetime import time

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.database.database import get_db
from app.models.enums import CargoUsuario
from app.models.models import BloqueioAgenda, Usuario
from app.schemas.entities import BloqueioCreate, BloqueioOut
from app.services.audit import add_audit_log
from app.services.db_utils import commit_or_conflict
from app.services.ownership import require_user

router = APIRouter(prefix="/bloqueios-agenda", tags=["Bloqueios da agenda"])


def _validar_bloqueio(
    data_inicio,
    data_fim,
    hora_inicio: time | None,
    hora_fim: time | None,
) -> None:
    if data_fim < data_inicio:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "A data final não pode ser menor que a inicial.",
        )

    if (hora_inicio is None) != (hora_fim is None):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Informe o horário inicial e final do bloqueio.",
        )

    if hora_inicio is None or hora_fim is None:
        return

    if data_inicio != data_fim:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Um bloqueio por horário deve ocorrer em uma única data.",
        )

    if hora_inicio >= hora_fim:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "O horário inicial deve ser menor que o final.",
        )


@router.get("", response_model=list[BloqueioOut])
def listar_bloqueios(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BloqueioAgenda]:
    return list(
        db.scalars(
            select(BloqueioAgenda)
            .where(BloqueioAgenda.empresa_id == current_user.empresa_id)
            .order_by(
                BloqueioAgenda.data_inicio,
                BloqueioAgenda.hora_inicio,
            )
        )
    )


@router.post("", response_model=BloqueioOut, status_code=status.HTTP_201_CREATED)
def criar_bloqueio(
    data: BloqueioCreate,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> BloqueioAgenda:
    _validar_bloqueio(
        data.data_inicio,
        data.data_fim,
        data.hora_inicio,
        data.hora_fim,
    )
    if data.funcionario_id:
        require_user(db, current_user.empresa_id, data.funcionario_id)

    item = BloqueioAgenda(
        empresa_id=current_user.empresa_id,
        **data.model_dump(),
    )
    db.add(item)
    db.flush()
    add_audit_log(
        db,
        user=current_user,
        action="CRIOU_BLOQUEIO_AGENDA",
        entity="bloqueios_agenda",
        entity_id=item.id,
    )
    return commit_or_conflict(db, item)


@router.delete("/{bloqueio_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_bloqueio(
    bloqueio_id: int,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> Response:
    item = db.scalar(
        select(BloqueioAgenda).where(
            BloqueioAgenda.id == bloqueio_id,
            BloqueioAgenda.empresa_id == current_user.empresa_id,
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bloqueio não encontrado.")
    db.delete(item)
    add_audit_log(
        db,
        user=current_user,
        action="EXCLUIU_BLOQUEIO_AGENDA",
        entity="bloqueios_agenda",
        entity_id=bloqueio_id,
    )
    commit_or_conflict(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
