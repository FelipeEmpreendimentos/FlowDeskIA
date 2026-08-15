from datetime import datetime, timedelta, timezone
from threading import Lock
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import or_, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.enums import StatusAgendamento
from app.models.models import Agendamento


AUTO_CANCEL_AFTER = timedelta(days=7)
CLEANUP_INTERVAL = timedelta(minutes=30)
_last_cleanup_by_company: dict[int, datetime] = {}
_cleanup_reservation_lock = Lock()


def auto_cancel_stale_appointments(
    db: Session,
    *,
    empresa_id: int,
    timezone_name: str,
) -> int:
    """Cancela atendimentos esquecidos após sete dias completos.

    A rotina é oportunista: roda no máximo uma vez a cada 30 minutos por empresa
    em cada processo da API. O registro não é excluído; ele passa para CANCELADO,
    deixa a Agenda ativa e permanece disponível no Histórico.

    A reserva é feita antes do acesso ao banco para impedir que o primeiro lote
    de requisições concorrentes da aplicação execute a mesma manutenção várias
    vezes em paralelo.
    """
    now_utc = datetime.now(timezone.utc)
    with _cleanup_reservation_lock:
        last_cleanup = _last_cleanup_by_company.get(empresa_id)
        if last_cleanup and now_utc - last_cleanup < CLEANUP_INTERVAL:
            return 0
        _last_cleanup_by_company[empresa_id] = now_utc

    try:
        company_timezone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        company_timezone = timezone.utc

    threshold_local = now_utc.astimezone(company_timezone) - AUTO_CANCEL_AFTER
    threshold_date = threshold_local.date()
    threshold_time = threshold_local.time().replace(tzinfo=None)

    try:
        result = db.execute(
            update(Agendamento)
            .where(
                Agendamento.empresa_id == empresa_id,
                Agendamento.status.notin_(
                    (
                        StatusAgendamento.FINALIZADO,
                        StatusAgendamento.CANCELADO,
                    )
                ),
                or_(
                    Agendamento.data < threshold_date,
                    (
                        (Agendamento.data == threshold_date)
                        & (Agendamento.hora_fim <= threshold_time)
                    ),
                ),
            )
            .values(
                status=StatusAgendamento.CANCELADO,
                cancelado_em=now_utc,
            )
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        return 0

    return int(result.rowcount or 0)
