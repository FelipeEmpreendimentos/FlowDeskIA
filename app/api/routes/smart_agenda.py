from datetime import date, time

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.api.routes import agenda as agenda_routes
from app.core.permissions import is_management
from app.database.database import get_db
from app.models.enums import CargoUsuario
from app.models.models import Agendamento, Usuario
from app.schemas.agenda_availability import SlotDisponivelDetalhado
from app.schemas.entities import AgendamentoCreate, AgendamentoOut, AgendamentoUpdate
from app.services.agenda import add_minutes, available_slots, ensure_available
from app.services.ownership import require_service, require_user
from app.services.service_assignment import (
    ensure_employee_qualified,
    qualification_map,
    save_service_qualification,
    smart_available_slots,
    smart_employee_for_slot,
)


router = APIRouter(tags=["Agenda inteligente"])


class QualificacaoServicoOut(BaseModel):
    servico_id: int
    funcionario_ids: list[int]


class QualificacaoServicoUpdate(BaseModel):
    funcionario_ids: list[int] = Field(min_length=1)


@router.get(
    "/servicos-qualificacoes",
    response_model=list[QualificacaoServicoOut],
)
def listar_qualificacoes(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[QualificacaoServicoOut]:
    mapa = qualification_map(db, empresa_id=current_user.empresa_id)
    return [
        QualificacaoServicoOut(
            servico_id=servico_id,
            funcionario_ids=funcionario_ids,
        )
        for servico_id, funcionario_ids in mapa.items()
    ]


@router.put(
    "/servicos/{servico_id}/funcionarios",
    response_model=QualificacaoServicoOut,
)
def atualizar_qualificacao(
    servico_id: int,
    data: QualificacaoServicoUpdate,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> QualificacaoServicoOut:
    require_service(db, current_user.empresa_id, servico_id)
    funcionario_ids = save_service_qualification(
        db,
        empresa_id=current_user.empresa_id,
        servico_id=servico_id,
        funcionario_ids=data.funcionario_ids,
    )
    return QualificacaoServicoOut(
        servico_id=servico_id,
        funcionario_ids=funcionario_ids,
    )


def _ensure_personal_appointment(
    item: Agendamento,
    current_user: Usuario,
) -> None:
    if is_management(current_user):
        return
    if item.funcionario_id != current_user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Com Visualizar Agenda você pode acessar somente os seus agendamentos.",
        )


def _personal_employee_id(
    current_user: Usuario,
    requested_employee_id: int | None,
) -> int | None:
    if is_management(current_user):
        return requested_employee_id
    if requested_employee_id not in (None, current_user.id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Para escolher outro funcionário é necessário Gerenciar Agenda.",
        )
    return current_user.id


# Estas rotas são registradas antes da Agenda legada. Assim a camada pública
# aplica escopo de permissão, qualificação por serviço e distribuição inteligente
# sem manter regras diferentes entre portal e futuras integrações.
@router.get("/agendamentos", response_model=list[AgendamentoOut])
def listar_agendamentos_com_escopo(
    data_inicio: date | None = None,
    data_fim: date | None = None,
    status_agendamento=None,
    funcionario_id: int | None = None,
    cliente_id: int | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Agendamento]:
    funcionario_efetivo = _personal_employee_id(current_user, funcionario_id)
    return agenda_routes.listar_agendamentos(
        data_inicio=data_inicio,
        data_fim=data_fim,
        status_agendamento=status_agendamento,
        funcionario_id=funcionario_efetivo,
        cliente_id=cliente_id,
        offset=offset,
        limit=limit,
        current_user=current_user,
        db=db,
    )


@router.get(
    "/agendamentos/disponibilidade",
    response_model=list[SlotDisponivelDetalhado],
)
def consultar_disponibilidade_inteligente(
    data: date,
    servico_id: int,
    funcionario_id: int | None = None,
    intervalo_minutos: int = Query(30, ge=5, le=240),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SlotDisponivelDetalhado]:
    servico = require_service(db, current_user.empresa_id, servico_id)
    funcionario_efetivo = _personal_employee_id(current_user, funcionario_id)

    if funcionario_efetivo is not None:
        funcionario = require_user(
            db,
            current_user.empresa_id,
            funcionario_efetivo,
        )
        ensure_employee_qualified(
            db,
            empresa_id=current_user.empresa_id,
            servico_id=servico.id,
            funcionario_id=funcionario.id,
        )
        slots = available_slots(
            db,
            empresa_id=current_user.empresa_id,
            target_date=data,
            funcionario_id=funcionario.id,
            service=servico,
            interval_minutes=intervalo_minutos,
        )
        return [
            SlotDisponivelDetalhado(
                hora_inicio=start,
                hora_fim=end,
                funcionario_id=funcionario.id,
                funcionario_nome=funcionario.nome,
            )
            for start, end in slots
        ]

    slots = smart_available_slots(
        db,
        empresa_id=current_user.empresa_id,
        target_date=data,
        service=servico,
        interval_minutes=intervalo_minutos,
    )
    nomes = {
        item.id: item.nome
        for item in db.scalars(
            select(Usuario).where(
                Usuario.empresa_id == current_user.empresa_id,
                Usuario.ativo.is_(True),
            )
        )
    }
    return [
        SlotDisponivelDetalhado(
            hora_inicio=start,
            hora_fim=end,
            funcionario_id=employee_id,
            funcionario_nome=nomes.get(
                employee_id,
                f"Usuário #{employee_id}",
            ),
        )
        for start, end, employee_id in slots
    ]


class AtribuicaoAutomaticaOut(BaseModel):
    funcionario_id: int
    funcionario_nome: str
    hora_inicio: time
    hora_fim: time


@router.get(
    "/agendamentos/atribuicao-automatica",
    response_model=AtribuicaoAutomaticaOut,
)
def atribuir_funcionario_automaticamente(
    data: date,
    servico_id: int,
    hora_inicio: time,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AtribuicaoAutomaticaOut:
    """Ponto único para portal, futura IA e WhatsApp usarem a mesma regra."""
    servico = require_service(db, current_user.empresa_id, servico_id)
    hora_fim = add_minutes(hora_inicio, servico.duracao_minutos)

    if is_management(current_user):
        funcionario_id = smart_employee_for_slot(
            db,
            empresa_id=current_user.empresa_id,
            target_date=data,
            service=servico,
            start=hora_inicio,
            end=hora_fim,
        )
    else:
        funcionario_id = current_user.id
        ensure_employee_qualified(
            db,
            empresa_id=current_user.empresa_id,
            servico_id=servico.id,
            funcionario_id=funcionario_id,
        )
        ensure_available(
            db,
            empresa_id=current_user.empresa_id,
            target_date=data,
            start=hora_inicio,
            end=hora_fim,
            funcionario_id=funcionario_id,
        )

    funcionario = require_user(db, current_user.empresa_id, funcionario_id)
    return AtribuicaoAutomaticaOut(
        funcionario_id=funcionario.id,
        funcionario_nome=funcionario.nome,
        hora_inicio=hora_inicio,
        hora_fim=hora_fim,
    )


@router.post(
    "/agendamentos",
    response_model=AgendamentoOut,
    status_code=status.HTTP_201_CREATED,
)
def criar_agendamento_com_escopo(
    data: AgendamentoCreate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Agendamento:
    servico = require_service(db, current_user.empresa_id, data.servico_id)
    requested_employee_id = _personal_employee_id(
        current_user,
        data.funcionario_id,
    )
    hora_fim = data.hora_fim or add_minutes(
        data.hora_inicio,
        servico.duracao_minutos,
    )

    if requested_employee_id is None:
        employee_id = smart_employee_for_slot(
            db,
            empresa_id=current_user.empresa_id,
            target_date=data.data,
            service=servico,
            start=data.hora_inicio,
            end=hora_fim,
        )
    else:
        employee_id = requested_employee_id
        require_user(db, current_user.empresa_id, employee_id)
        ensure_employee_qualified(
            db,
            empresa_id=current_user.empresa_id,
            servico_id=servico.id,
            funcionario_id=employee_id,
        )

    adjusted = data.model_copy(update={"funcionario_id": employee_id})
    return agenda_routes.criar_agendamento(
        data=adjusted,
        current_user=current_user,
        db=db,
    )


@router.get("/agendamentos/{agendamento_id}", response_model=AgendamentoOut)
def obter_agendamento_com_escopo(
    agendamento_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Agendamento:
    item = agenda_routes.obter_agendamento(
        agendamento_id=agendamento_id,
        current_user=current_user,
        db=db,
    )
    _ensure_personal_appointment(item, current_user)
    return item


@router.patch("/agendamentos/{agendamento_id}", response_model=AgendamentoOut)
def atualizar_agendamento_com_escopo(
    agendamento_id: int,
    data: AgendamentoUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Agendamento:
    item = agenda_routes.obter_agendamento(
        agendamento_id=agendamento_id,
        current_user=current_user,
        db=db,
    )
    _ensure_personal_appointment(item, current_user)

    values = data.model_dump(exclude_unset=True)
    if not is_management(current_user):
        requested_employee = values.get("funcionario_id", current_user.id)
        if requested_employee != current_user.id:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Para escolher ou trocar o funcionário é necessário Gerenciar Agenda.",
            )
        target_employee_id = current_user.id
    else:
        target_employee_id = values.get("funcionario_id", item.funcionario_id)

    target_service_id = values.get("servico_id", item.servico_id)
    require_service(db, current_user.empresa_id, target_service_id)
    if target_employee_id is not None:
        require_user(db, current_user.empresa_id, target_employee_id)
        ensure_employee_qualified(
            db,
            empresa_id=current_user.empresa_id,
            servico_id=target_service_id,
            funcionario_id=target_employee_id,
        )

    return agenda_routes.atualizar_agendamento(
        agendamento_id=agendamento_id,
        data=data,
        current_user=current_user,
        db=db,
    )


@router.delete(
    "/agendamentos/{agendamento_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def cancelar_agendamento_com_escopo(
    agendamento_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    item = agenda_routes.obter_agendamento(
        agendamento_id=agendamento_id,
        current_user=current_user,
        db=db,
    )
    _ensure_personal_appointment(item, current_user)
    return agenda_routes.cancelar_agendamento(
        agendamento_id=agendamento_id,
        current_user=current_user,
        db=db,
    )
