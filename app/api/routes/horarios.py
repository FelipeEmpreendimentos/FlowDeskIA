from datetime import time

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.database.database import get_db
from app.models.enums import CargoUsuario
from app.models.models import Horario, Usuario
from app.schemas.entities import HorarioCreate, HorarioOut, HorarioUpdate
from app.services.audit import add_audit_log
from app.services.db_utils import apply_patch, commit_or_conflict
from app.services.ownership import require_user

router = APIRouter(prefix="/horarios", tags=["Horários"])


def _get(db: Session, empresa_id: int, horario_id: int) -> Horario:
    item = db.scalar(
        select(Horario).where(
            Horario.id == horario_id,
            Horario.empresa_id == empresa_id,
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Horário não encontrado.")
    return item


def _validar_jornada(
    inicio: time,
    fim: time,
    pausa_inicio: time | None,
    pausa_fim: time | None,
) -> None:
    if inicio >= fim:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "A hora inicial deve ser menor que a hora final.",
        )

    if (pausa_inicio is None) != (pausa_fim is None):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Informe o início e o fim do horário de almoço.",
        )

    if pausa_inicio is None or pausa_fim is None:
        return

    if pausa_inicio >= pausa_fim:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "O início do almoço deve ser menor que o fim.",
        )

    if pausa_inicio < inicio or pausa_fim > fim:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "O horário de almoço deve ficar dentro da jornada de trabalho.",
        )


@router.get("", response_model=list[HorarioOut])
def listar_horarios(
    funcionario_id: int | None = None,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Horario]:
    query = select(Horario).where(Horario.empresa_id == current_user.empresa_id)
    if funcionario_id:
        query = query.where(Horario.funcionario_id == funcionario_id)
    return list(
        db.scalars(query.order_by(Horario.dia_semana, Horario.hora_inicio))
    )


@router.post("", response_model=HorarioOut, status_code=status.HTTP_201_CREATED)
def criar_horario(
    data: HorarioCreate,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> Horario:
    require_user(db, current_user.empresa_id, data.funcionario_id)
    _validar_jornada(
        data.hora_inicio,
        data.hora_fim,
        data.pausa_inicio,
        data.pausa_fim,
    )
    item = Horario(empresa_id=current_user.empresa_id, **data.model_dump())
    db.add(item)
    db.flush()
    add_audit_log(
        db,
        user=current_user,
        action="CRIOU_HORARIO",
        entity="horarios",
        entity_id=item.id,
    )
    return commit_or_conflict(db, item)


@router.patch("/{horario_id}", response_model=HorarioOut)
def atualizar_horario(
    horario_id: int,
    data: HorarioUpdate,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> Horario:
    item = _get(db, current_user.empresa_id, horario_id)
    values = data.model_dump(exclude_unset=True)
    inicio = values.get("hora_inicio", item.hora_inicio)
    fim = values.get("hora_fim", item.hora_fim)
    pausa_inicio = values.get("pausa_inicio", item.pausa_inicio)
    pausa_fim = values.get("pausa_fim", item.pausa_fim)
    _validar_jornada(inicio, fim, pausa_inicio, pausa_fim)
    apply_patch(item, values)
    add_audit_log(
        db,
        user=current_user,
        action="ATUALIZOU_HORARIO",
        entity="horarios",
        entity_id=item.id,
    )
    return commit_or_conflict(db, item)


@router.delete("/{horario_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_horario(
    horario_id: int,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> Response:
    item = _get(db, current_user.empresa_id, horario_id)
    entity_id = item.id
    db.delete(item)
    add_audit_log(
        db,
        user=current_user,
        action="EXCLUIU_HORARIO",
        entity="horarios",
        entity_id=entity_id,
    )
    commit_or_conflict(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
