from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.agenda_settings import ConfiguracaoAgenda
from app.models.enums import StatusAgendamento
from app.models.models import (
    Agendamento,
    BloqueioAgenda,
    Empresa,
    Horario,
    Servico,
)


INTERVALOS_PERMITIDOS = {15, 30, 60}


def add_minutes(value: time, minutes: int) -> time:
    base = datetime.combine(date.today(), value)
    return (base + timedelta(minutes=minutes)).time()


def validate_time_range(start: time, end: time) -> None:
    if start >= end:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "A hora inicial deve ser menor que a hora final.",
        )


def _employee_block_filter(funcionario_id: int | None):
    if funcionario_id is None:
        return BloqueioAgenda.funcionario_id.is_(None)
    return or_(
        BloqueioAgenda.funcionario_id.is_(None),
        BloqueioAgenda.funcionario_id == funcionario_id,
    )


def _company_now(db: Session, empresa_id: int) -> datetime:
    empresa = db.get(Empresa, empresa_id)
    timezone_name = empresa.timezone if empresa and empresa.timezone else "America/Sao_Paulo"

    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        timezone = ZoneInfo("America/Sao_Paulo")

    return datetime.now(timezone)


def _configured_interval(
    db: Session,
    empresa_id: int,
    fallback: int,
) -> int:
    configuracao = db.get(ConfiguracaoAgenda, empresa_id)
    intervalo = configuracao.intervalo_minutos if configuracao else fallback
    return intervalo if intervalo in INTERVALOS_PERMITIDOS else 30


def is_day_fully_blocked(
    db: Session,
    *,
    empresa_id: int,
    target_date: date,
    funcionario_id: int | None,
) -> bool:
    query = select(BloqueioAgenda.id).where(
        BloqueioAgenda.empresa_id == empresa_id,
        BloqueioAgenda.data_inicio <= target_date,
        BloqueioAgenda.data_fim >= target_date,
        BloqueioAgenda.hora_inicio.is_(None),
        BloqueioAgenda.hora_fim.is_(None),
        _employee_block_filter(funcionario_id),
    )
    return db.scalar(query.limit(1)) is not None


def has_blockage_conflict(
    db: Session,
    *,
    empresa_id: int,
    target_date: date,
    start: time,
    end: time,
    funcionario_id: int | None,
) -> bool:
    query = select(BloqueioAgenda.id).where(
        BloqueioAgenda.empresa_id == empresa_id,
        BloqueioAgenda.data_inicio <= target_date,
        BloqueioAgenda.data_fim >= target_date,
        _employee_block_filter(funcionario_id),
        or_(
            BloqueioAgenda.hora_inicio.is_(None),
            BloqueioAgenda.hora_fim.is_(None),
            (
                (BloqueioAgenda.hora_inicio < end)
                & (BloqueioAgenda.hora_fim > start)
            ),
        ),
    )
    return db.scalar(query.limit(1)) is not None


def has_conflict(
    db: Session,
    *,
    empresa_id: int,
    target_date: date,
    start: time,
    end: time,
    funcionario_id: int | None,
    ignore_id: int | None = None,
) -> bool:
    if funcionario_id is None:
        return False

    query = select(Agendamento.id).where(
        Agendamento.empresa_id == empresa_id,
        Agendamento.funcionario_id == funcionario_id,
        Agendamento.data == target_date,
        Agendamento.status != StatusAgendamento.CANCELADO,
        Agendamento.hora_inicio < end,
        Agendamento.hora_fim > start,
    )

    if ignore_id is not None:
        query = query.where(Agendamento.id != ignore_id)

    return db.scalar(query.limit(1)) is not None


def _overlaps_pause(schedule: Horario, start: time, end: time) -> bool:
    if schedule.pausa_inicio is None or schedule.pausa_fim is None:
        return False
    return start < schedule.pausa_fim and end > schedule.pausa_inicio


def is_within_work_schedule(
    db: Session,
    *,
    empresa_id: int,
    target_date: date,
    start: time,
    end: time,
    funcionario_id: int,
) -> bool:
    weekday = (target_date.weekday() + 1) % 7
    schedules = db.scalars(
        select(Horario).where(
            Horario.empresa_id == empresa_id,
            Horario.funcionario_id == funcionario_id,
            Horario.dia_semana == weekday,
            Horario.ativo.is_(True),
        )
    ).all()

    return any(
        start >= schedule.hora_inicio
        and end <= schedule.hora_fim
        and not _overlaps_pause(schedule, start, end)
        for schedule in schedules
    )


def ensure_available(
    db: Session,
    *,
    empresa_id: int,
    target_date: date,
    start: time,
    end: time,
    funcionario_id: int | None,
    ignore_id: int | None = None,
) -> None:
    validate_time_range(start, end)

    if funcionario_id is not None and not is_within_work_schedule(
        db,
        empresa_id=empresa_id,
        target_date=target_date,
        start=start,
        end=end,
        funcionario_id=funcionario_id,
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "O horário está fora da jornada ou coincide com o intervalo do funcionário.",
        )

    if has_blockage_conflict(
        db,
        empresa_id=empresa_id,
        target_date=target_date,
        start=start,
        end=end,
        funcionario_id=funcionario_id,
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A agenda está bloqueada nesse período.",
        )

    if has_conflict(
        db,
        empresa_id=empresa_id,
        target_date=target_date,
        start=start,
        end=end,
        funcionario_id=funcionario_id,
        ignore_id=ignore_id,
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Já existe um agendamento nesse horário para o funcionário.",
        )


def available_slots(
    db: Session,
    *,
    empresa_id: int,
    target_date: date,
    funcionario_id: int,
    service: Servico,
    interval_minutes: int,
) -> list[tuple[time, time]]:
    now_local = _company_now(db, empresa_id)
    if target_date < now_local.date():
        return []

    minimum_start = (
        now_local.time().replace(tzinfo=None)
        if target_date == now_local.date()
        else None
    )
    interval_minutes = _configured_interval(
        db,
        empresa_id,
        interval_minutes,
    )

    weekday = (target_date.weekday() + 1) % 7
    schedules = db.scalars(
        select(Horario).where(
            Horario.empresa_id == empresa_id,
            Horario.funcionario_id == funcionario_id,
            Horario.dia_semana == weekday,
            Horario.ativo.is_(True),
        )
    ).all()

    if is_day_fully_blocked(
        db,
        empresa_id=empresa_id,
        target_date=target_date,
        funcionario_id=funcionario_id,
    ):
        return []

    slots: dict[tuple[time, time], None] = {}

    for schedule in schedules:
        cursor = schedule.hora_inicio
        while True:
            end = add_minutes(cursor, service.duracao_minutos)
            if end > schedule.hora_fim or end <= cursor:
                break

            horario_passado = minimum_start is not None and cursor < minimum_start
            indisponivel = (
                horario_passado
                or _overlaps_pause(schedule, cursor, end)
                or has_blockage_conflict(
                    db,
                    empresa_id=empresa_id,
                    target_date=target_date,
                    start=cursor,
                    end=end,
                    funcionario_id=funcionario_id,
                )
                or has_conflict(
                    db,
                    empresa_id=empresa_id,
                    target_date=target_date,
                    start=cursor,
                    end=end,
                    funcionario_id=funcionario_id,
                )
            )

            if not indisponivel:
                slots[(cursor, end)] = None

            next_cursor = add_minutes(cursor, interval_minutes)
            if next_cursor <= cursor:
                break
            cursor = next_cursor

    return sorted(slots.keys(), key=lambda item: item[0])
