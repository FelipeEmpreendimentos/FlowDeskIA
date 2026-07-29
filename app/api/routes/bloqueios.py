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
from app.services.notifications import notify_management, notify_user
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


def _descricao_bloqueio(item: BloqueioAgenda) -> str:
    periodo = item.data_inicio.strftime("%d/%m/%Y")
    if item.data_fim != item.data_inicio:
        periodo += f" até {item.data_fim.strftime('%d/%m/%Y')}"
    if item.hora_inicio and item.hora_fim:
        periodo += (
            f", das {item.hora_inicio.strftime('%H:%M')} "
            f"às {item.hora_fim.strftime('%H:%M')}"
        )
    return periodo


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

    descricao = _descricao_bloqueio(item)
    if item.funcionario_id and item.funcionario_id != current_user.id:
        notify_user(
            db,
            empresa_id=current_user.empresa_id,
            usuario_id=item.funcionario_id,
            titulo="Novo bloqueio na sua agenda",
            mensagem=f"Sua agenda foi bloqueada em {descricao}.",
        )

    notify_management(
        db,
        empresa_id=current_user.empresa_id,
        titulo="Bloqueio de agenda criado",
        mensagem=f"{current_user.nome} criou um bloqueio em {descricao}.",
        exclude_user_ids=(current_user.id,),
    )
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

    descricao = _descricao_bloqueio(item)
    affected_user_id = item.funcionario_id
    db.delete(item)

    if affected_user_id and affected_user_id != current_user.id:
        notify_user(
            db,
            empresa_id=current_user.empresa_id,
            usuario_id=affected_user_id,
            titulo="Bloqueio removido da sua agenda",
            mensagem=f"O bloqueio de {descricao} foi removido.",
        )

    notify_management(
        db,
        empresa_id=current_user.empresa_id,
        titulo="Bloqueio de agenda removido",
        mensagem=f"{current_user.nome} removeu o bloqueio de {descricao}.",
        exclude_user_ids=(current_user.id,),
    )
    add_audit_log(
        db,
        user=current_user,
        action="EXCLUIU_BLOQUEIO_AGENDA",
        entity="bloqueios_agenda",
        entity_id=bloqueio_id,
    )
    commit_or_conflict(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
