from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.permissions import is_management, validate_employee_appointment_update
from app.database.database import get_db
from app.models.enums import CargoUsuario, StatusAgendamento
from app.models.models import Agendamento, Servico, Usuario, Veiculo
from app.schemas.agenda_availability import SlotDisponivelDetalhado
from app.schemas.entities import (
    AgendamentoCreate,
    AgendamentoOut,
    AgendamentoUpdate,
)
from app.services.agenda import (
    add_minutes,
    available_slots,
    available_slots_for_any_employee,
    choose_available_employee,
    ensure_available,
)
from app.services.audit import add_audit_log
from app.services.db_utils import apply_patch, commit_or_conflict
from app.services.notifications import notify_management, notify_user
from app.services.ownership import (
    require_client,
    require_service,
    require_user,
    require_vehicle,
)

router = APIRouter(prefix="/agendamentos", tags=["Agendamentos"])


def _get_appointment(db: Session, empresa_id: int, agendamento_id: int) -> Agendamento:
    item = db.scalar(
        select(Agendamento).where(
            Agendamento.id == agendamento_id,
            Agendamento.empresa_id == empresa_id,
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agendamento não encontrado.")
    return item


def _resolve_tipo_veiculo(
    veiculo: Veiculo | None,
    tipo_informado: str | None,
) -> str | None:
    if veiculo is not None and veiculo.tipo_veiculo:
        return veiculo.tipo_veiculo
    return tipo_informado


def _calcular_preco(
    servico: Servico,
    tipo_veiculo: str | None,
) -> tuple[Decimal, Decimal, Decimal]:
    valor_base = Decimal(servico.preco)
    valor_adicional = Decimal("0.00")

    if servico.adicional_por_tipo_ativo:
        if not tipo_veiculo:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Selecione o tipo do veículo para calcular o valor do serviço.",
            )

        adicional = next(
            (
                item
                for item in servico.adicionais
                if item.tipo_veiculo == tipo_veiculo
            ),
            None,
        )
        if adicional is not None:
            valor_adicional = Decimal(adicional.valor_adicional)

    return valor_base, valor_adicional, valor_base + valor_adicional


def _formatar_horario(data_agendamento: date, hora_inicio) -> str:
    return f"{data_agendamento.strftime('%d/%m/%Y')} às {hora_inicio.strftime('%H:%M')}"


def _registrar_conflito(
    db: Session,
    *,
    current_user: Usuario,
    data_agendamento: date,
    hora_inicio,
    detalhe: str,
) -> None:
    notify_management(
        db,
        empresa_id=current_user.empresa_id,
        titulo="Conflito de agenda identificado",
        mensagem=(
            f"{current_user.nome} tentou agendar em "
            f"{_formatar_horario(data_agendamento, hora_inicio)}. {detalhe}"
        ),
        exclude_user_ids=(current_user.id,),
    )
    db.commit()


@router.get("", response_model=list[AgendamentoOut])
def listar_agendamentos(
    data_inicio: date | None = None,
    data_fim: date | None = None,
    status_agendamento: StatusAgendamento | None = None,
    funcionario_id: int | None = None,
    cliente_id: int | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Agendamento]:
    query = select(Agendamento).where(
        Agendamento.empresa_id == current_user.empresa_id
    )
    if data_inicio:
        query = query.where(Agendamento.data >= data_inicio)
    if data_fim:
        query = query.where(Agendamento.data <= data_fim)
    if status_agendamento:
        query = query.where(Agendamento.status == status_agendamento)
    if funcionario_id:
        query = query.where(Agendamento.funcionario_id == funcionario_id)
    if cliente_id:
        query = query.where(Agendamento.cliente_id == cliente_id)
    query = query.order_by(Agendamento.data, Agendamento.hora_inicio)
    return list(db.scalars(query.offset(offset).limit(limit)))


@router.get("/disponibilidade", response_model=list[SlotDisponivelDetalhado])
def consultar_disponibilidade(
    data: date,
    servico_id: int,
    funcionario_id: int | None = None,
    intervalo_minutos: int = Query(30, ge=5, le=240),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SlotDisponivelDetalhado]:
    servico = require_service(db, current_user.empresa_id, servico_id)

    if funcionario_id is not None:
        funcionario = require_user(db, current_user.empresa_id, funcionario_id)
        slots = available_slots(
            db,
            empresa_id=current_user.empresa_id,
            target_date=data,
            funcionario_id=funcionario_id,
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

    slots_gerais = available_slots_for_any_employee(
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
            funcionario_nome=nomes.get(employee_id, f"Usuário #{employee_id}"),
        )
        for start, end, employee_id in slots_gerais
    ]


@router.post("", response_model=AgendamentoOut, status_code=status.HTTP_201_CREATED)
def criar_agendamento(
    data: AgendamentoCreate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Agendamento:
    if data.status == StatusAgendamento.CANCELADO:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Um novo agendamento não pode ser criado como cancelado.",
        )

    cliente = require_client(db, current_user.empresa_id, data.cliente_id)
    servico = require_service(db, current_user.empresa_id, data.servico_id)

    veiculo: Veiculo | None = None
    if data.veiculo_id:
        veiculo = require_vehicle(db, current_user.empresa_id, data.veiculo_id)
        if veiculo.cliente_id != data.cliente_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "O veículo não pertence ao cliente informado.",
            )

    tipo_veiculo = _resolve_tipo_veiculo(veiculo, data.tipo_veiculo)
    valor_base, valor_adicional, valor_final = _calcular_preco(
        servico,
        tipo_veiculo,
    )
    end = data.hora_fim or add_minutes(data.hora_inicio, servico.duracao_minutos)

    funcionario_id = data.funcionario_id
    if funcionario_id is not None:
        require_user(db, current_user.empresa_id, funcionario_id)
    else:
        funcionario_id = choose_available_employee(
            db,
            empresa_id=current_user.empresa_id,
            target_date=data.data,
            start=data.hora_inicio,
            end=end,
        )

    try:
        ensure_available(
            db,
            empresa_id=current_user.empresa_id,
            target_date=data.data,
            start=data.hora_inicio,
            end=end,
            funcionario_id=funcionario_id,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_409_CONFLICT:
            _registrar_conflito(
                db,
                current_user=current_user,
                data_agendamento=data.data,
                hora_inicio=data.hora_inicio,
                detalhe=str(exc.detail),
            )
        raise

    values = data.model_dump(
        exclude={"hora_fim", "valor_final", "tipo_veiculo", "funcionario_id"}
    )
    appointment = Agendamento(
        empresa_id=current_user.empresa_id,
        funcionario_id=funcionario_id,
        hora_fim=end,
        valor_base=valor_base,
        valor_adicional=valor_adicional,
        valor_final=valor_final,
        tipo_veiculo_cobrado=tipo_veiculo,
        **values,
    )

    now = datetime.now(timezone.utc)
    if appointment.status == StatusAgendamento.CONFIRMADO:
        appointment.confirmado_em = now

    db.add(appointment)
    db.flush()

    if appointment.funcionario_id and appointment.funcionario_id != current_user.id:
        notify_user(
            db,
            empresa_id=current_user.empresa_id,
            usuario_id=appointment.funcionario_id,
            titulo="Novo agendamento atribuído",
            mensagem=(
                f"{cliente.nome} - {servico.nome}, "
                f"{_formatar_horario(appointment.data, appointment.hora_inicio)}."
            ),
        )

    add_audit_log(
        db,
        user=current_user,
        action="CRIOU_AGENDAMENTO",
        entity="agendamentos",
        entity_id=appointment.id,
        details={
            "valor_base": str(valor_base),
            "valor_adicional": str(valor_adicional),
            "valor_final": str(valor_final),
            "tipo_veiculo": tipo_veiculo,
            "funcionario_atribuido": funcionario_id,
            "atribuicao_automatica": data.funcionario_id is None,
        },
    )
    return commit_or_conflict(db, appointment)


@router.get("/{agendamento_id}", response_model=AgendamentoOut)
def obter_agendamento(
    agendamento_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Agendamento:
    return _get_appointment(db, current_user.empresa_id, agendamento_id)


@router.patch("/{agendamento_id}", response_model=AgendamentoOut)
def atualizar_agendamento(
    agendamento_id: int,
    data: AgendamentoUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Agendamento:
    appointment = _get_appointment(db, current_user.empresa_id, agendamento_id)
    values = data.model_dump(exclude_unset=True)
    validate_employee_appointment_update(current_user, appointment, values)

    old_status = appointment.status
    old_employee_id = appointment.funcionario_id
    tipo_informado = values.pop("tipo_veiculo", appointment.tipo_veiculo_cobrado)
    values.pop("valor_final", None)

    target_service_id = values.get("servico_id", appointment.servico_id)
    service = require_service(db, current_user.empresa_id, target_service_id)

    target_vehicle_id = values.get("veiculo_id", appointment.veiculo_id)
    vehicle: Veiculo | None = None
    if target_vehicle_id:
        vehicle = require_vehicle(db, current_user.empresa_id, target_vehicle_id)
        if vehicle.cliente_id != appointment.cliente_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "O veículo não pertence ao cliente do agendamento.",
            )
    if values.get("funcionario_id"):
        require_user(db, current_user.empresa_id, values["funcionario_id"])

    target_date = values.get("data", appointment.data)
    start = values.get("hora_inicio", appointment.hora_inicio)
    end = values.get("hora_fim")
    if end is None:
        if "hora_inicio" in values or "servico_id" in values:
            end = add_minutes(start, service.duracao_minutos)
            values["hora_fim"] = end
        else:
            end = appointment.hora_fim

    target_employee = values.get("funcionario_id", appointment.funcionario_id)
    if not is_management(current_user) and target_employee is None:
        target_employee = current_user.id
    elif target_employee is None:
        target_employee = choose_available_employee(
            db,
            empresa_id=current_user.empresa_id,
            target_date=target_date,
            start=start,
            end=end,
            ignore_id=appointment.id,
        )
        values["funcionario_id"] = target_employee

    try:
        ensure_available(
            db,
            empresa_id=current_user.empresa_id,
            target_date=target_date,
            start=start,
            end=end,
            funcionario_id=target_employee,
            ignore_id=appointment.id,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_409_CONFLICT:
            _registrar_conflito(
                db,
                current_user=current_user,
                data_agendamento=target_date,
                hora_inicio=start,
                detalhe=str(exc.detail),
            )
        raise

    if not is_management(current_user) and appointment.funcionario_id is None:
        appointment.funcionario_id = current_user.id

    tipo_veiculo = _resolve_tipo_veiculo(vehicle, tipo_informado)
    pricing_changed = (
        target_service_id != appointment.servico_id
        or target_vehicle_id != appointment.veiculo_id
        or tipo_veiculo != appointment.tipo_veiculo_cobrado
    )
    if pricing_changed:
        valor_base, valor_adicional, valor_final = _calcular_preco(
            service,
            tipo_veiculo,
        )
        values.update(
            valor_base=valor_base,
            valor_adicional=valor_adicional,
            valor_final=valor_final,
            tipo_veiculo_cobrado=tipo_veiculo,
        )

    apply_patch(appointment, values)
    now = datetime.now(timezone.utc)
    if appointment.status != old_status:
        if appointment.status == StatusAgendamento.CONFIRMADO:
            appointment.confirmado_em = now
        elif appointment.status == StatusAgendamento.CANCELADO:
            appointment.cancelado_em = now
        elif appointment.status == StatusAgendamento.FINALIZADO:
            appointment.finalizado_em = now

    employee_changed = appointment.funcionario_id != old_employee_id
    if appointment.funcionario_id and appointment.funcionario_id != current_user.id:
        titulo = (
            "Novo agendamento atribuído"
            if employee_changed
            else "Agendamento atualizado"
        )
        notify_user(
            db,
            empresa_id=current_user.empresa_id,
            usuario_id=appointment.funcionario_id,
            titulo=titulo,
            mensagem=_formatar_horario(appointment.data, appointment.hora_inicio),
        )

    if appointment.status == StatusAgendamento.CANCELADO and old_status != appointment.status:
        notify_management(
            db,
            empresa_id=current_user.empresa_id,
            titulo="Agendamento cancelado",
            mensagem=(
                f"Agendamento #{appointment.id} cancelado por {current_user.nome}."
            ),
            exclude_user_ids=(current_user.id,),
        )

    add_audit_log(
        db,
        user=current_user,
        action="ATUALIZOU_AGENDAMENTO",
        entity="agendamentos",
        entity_id=appointment.id,
        details={
            "preco_recalculado": pricing_changed,
            "valor_final": str(appointment.valor_final),
        },
    )
    return commit_or_conflict(db, appointment)


@router.delete("/{agendamento_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancelar_agendamento(
    agendamento_id: int,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> Response:
    appointment = _get_appointment(db, current_user.empresa_id, agendamento_id)
    appointment.status = StatusAgendamento.CANCELADO
    appointment.cancelado_em = datetime.now(timezone.utc)

    if appointment.funcionario_id and appointment.funcionario_id != current_user.id:
        notify_user(
            db,
            empresa_id=current_user.empresa_id,
            usuario_id=appointment.funcionario_id,
            titulo="Agendamento cancelado",
            mensagem=(
                f"O atendimento de {_formatar_horario(appointment.data, appointment.hora_inicio)} "
                "foi cancelado."
            ),
        )

    notify_management(
        db,
        empresa_id=current_user.empresa_id,
        titulo="Agendamento cancelado",
        mensagem=f"Agendamento #{appointment.id} cancelado por {current_user.nome}.",
        exclude_user_ids=(current_user.id,),
    )
    add_audit_log(
        db,
        user=current_user,
        action="CANCELOU_AGENDAMENTO",
        entity="agendamentos",
        entity_id=appointment.id,
    )
    commit_or_conflict(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
