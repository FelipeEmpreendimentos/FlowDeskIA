from datetime import time

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
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


class DiaJornadaSemanal(BaseModel):
    dia_semana: int = Field(ge=0, le=6)
    ativo: bool = True
    hora_inicio: time | None = None
    hora_fim: time | None = None
    pausa_inicio: time | None = None
    pausa_fim: time | None = None


class JornadaSemanalInput(BaseModel):
    dias: list[DiaJornadaSemanal]


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


@router.put("/semana/{funcionario_id}", response_model=list[HorarioOut])
def salvar_jornada_semanal(
    funcionario_id: int,
    data: JornadaSemanalInput,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> list[Horario]:
    """Substitui a semana inteira em uma única transação.

    O frontend antigo salvava cada dia em uma requisição separada. Isso podia
    deixar a jornada parcialmente atualizada quando uma chamada falhava. Aqui
    toda a configuração é validada antes de qualquer alteração no banco.
    """
    require_user(db, current_user.empresa_id, funcionario_id)

    if len(data.dias) != 7:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Envie a configuração dos sete dias da semana.",
        )

    por_dia: dict[int, DiaJornadaSemanal] = {}
    for configuracao in data.dias:
        if configuracao.dia_semana in por_dia:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Existe mais de uma configuração para o mesmo dia da semana.",
            )
        por_dia[configuracao.dia_semana] = configuracao

    if set(por_dia) != set(range(7)):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "A jornada precisa informar cada dia da semana uma única vez.",
        )

    for configuracao in por_dia.values():
        if not configuracao.ativo:
            continue
        if configuracao.hora_inicio is None or configuracao.hora_fim is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Informe o início e o fim de todos os dias trabalhados.",
            )
        _validar_jornada(
            configuracao.hora_inicio,
            configuracao.hora_fim,
            configuracao.pausa_inicio,
            configuracao.pausa_fim,
        )

    db.execute(
        delete(Horario).where(
            Horario.empresa_id == current_user.empresa_id,
            Horario.funcionario_id == funcionario_id,
        )
    )

    dias_ativos: list[int] = []
    for dia in range(7):
        configuracao = por_dia[dia]
        if not configuracao.ativo:
            continue

        item = Horario(
            empresa_id=current_user.empresa_id,
            funcionario_id=funcionario_id,
            dia_semana=dia,
            hora_inicio=configuracao.hora_inicio,
            hora_fim=configuracao.hora_fim,
            pausa_inicio=configuracao.pausa_inicio,
            pausa_fim=configuracao.pausa_fim,
            ativo=True,
        )
        db.add(item)
        dias_ativos.append(dia)

    db.flush()
    add_audit_log(
        db,
        user=current_user,
        action="SALVOU_JORNADA_SEMANAL",
        entity="horarios",
        entity_id=funcionario_id,
        details={
            "funcionario_id": funcionario_id,
            "dias_ativos": dias_ativos,
        },
    )
    commit_or_conflict(db)

    return list(
        db.scalars(
            select(Horario)
            .where(
                Horario.empresa_id == current_user.empresa_id,
                Horario.funcionario_id == funcionario_id,
            )
            .order_by(Horario.dia_semana, Horario.hora_inicio)
        )
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
