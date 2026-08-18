from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attendance import UserAttendancePresence
from app.models.enums import AtorLog, StatusConversa
from app.models.models import Conversa, Log, Usuario
from app.services.access_control import user_module_access
from app.services.notifications import notify_management, notify_user


STATUS_DISPONIVEL = "DISPONIVEL"
STATUS_AUSENTE = "AUSENTE"
STATUS_OFFLINE = "OFFLINE"
VALID_ATTENDANCE_STATUSES = {
    STATUS_DISPONIVEL,
    STATUS_AUSENTE,
    STATUS_OFFLINE,
}
PRESENCE_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class PresenceSnapshot:
    user_id: int
    empresa_id: int
    status: str
    effective_status: str
    heartbeat_at: datetime | None
    last_assignment_at: datetime | None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _presence_row(
    db: Session,
    *,
    user_id: int,
    empresa_id: int,
) -> UserAttendancePresence | None:
    return db.scalar(
        select(UserAttendancePresence).where(
            UserAttendancePresence.user_id == user_id,
            UserAttendancePresence.empresa_id == empresa_id,
        )
    )


def ensure_presence(
    db: Session,
    user: Usuario,
    *,
    initial_status: str = STATUS_DISPONIVEL,
) -> UserAttendancePresence:
    row = _presence_row(
        db,
        user_id=user.id,
        empresa_id=user.empresa_id,
    )
    if row is not None:
        return row

    now = _now()
    row = UserAttendancePresence(
        user_id=user.id,
        empresa_id=user.empresa_id,
        status=initial_status,
        heartbeat_at=now,
        last_assignment_at=None,
        updated_at=now,
    )
    db.add(row)
    db.flush()
    return row


def effective_status(
    row: UserAttendancePresence | None,
    *,
    now: datetime | None = None,
) -> str:
    if row is None:
        return STATUS_OFFLINE
    if row.status == STATUS_OFFLINE:
        return STATUS_OFFLINE
    if row.status not in VALID_ATTENDANCE_STATUSES:
        return STATUS_OFFLINE
    if row.heartbeat_at is None:
        return STATUS_OFFLINE

    reference = now or _now()
    cutoff = reference - timedelta(seconds=PRESENCE_TIMEOUT_SECONDS)
    if row.heartbeat_at < cutoff:
        return STATUS_OFFLINE
    return row.status


def snapshot(row: UserAttendancePresence) -> PresenceSnapshot:
    return PresenceSnapshot(
        user_id=row.user_id,
        empresa_id=row.empresa_id,
        status=row.status,
        effective_status=effective_status(row),
        heartbeat_at=row.heartbeat_at,
        last_assignment_at=row.last_assignment_at,
    )


def touch_heartbeat(db: Session, user: Usuario) -> PresenceSnapshot:
    row = ensure_presence(db, user)
    now = _now()
    row.heartbeat_at = now
    row.updated_at = now
    db.commit()
    return snapshot(row)


def set_presence_status(
    db: Session,
    user: Usuario,
    attendance_status: str,
) -> PresenceSnapshot:
    normalized = attendance_status.strip().upper()
    if normalized not in VALID_ATTENDANCE_STATUSES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Status de atendimento inválido.",
        )

    row = ensure_presence(db, user)
    now = _now()
    row.status = normalized
    row.heartbeat_at = now
    row.updated_at = now
    db.commit()
    return snapshot(row)


def get_presence_snapshot(
    db: Session,
    user: Usuario,
    *,
    touch: bool = False,
) -> PresenceSnapshot:
    row = ensure_presence(db, user)
    if touch:
        now = _now()
        row.heartbeat_at = now
        row.updated_at = now
        db.commit()
    elif row in db.new:
        db.commit()
    return snapshot(row)


def can_reply(db: Session, user: Usuario) -> bool:
    row = ensure_presence(db, user)
    if row in db.new:
        db.commit()
    return effective_status(row) != STATUS_OFFLINE


def require_can_reply(db: Session, user: Usuario) -> None:
    if can_reply(db, user):
        return
    raise HTTPException(
        status.HTTP_409_CONFLICT,
        "Seu status está Offline. Mude para Disponível ou Ausente antes de responder clientes.",
    )


def team_presence(
    db: Session,
    *,
    empresa_id: int,
) -> list[tuple[Usuario, PresenceSnapshot | None]]:
    users = list(
        db.scalars(
            select(Usuario)
            .where(
                Usuario.empresa_id == empresa_id,
                Usuario.ativo.is_(True),
            )
            .order_by(Usuario.nome, Usuario.id)
        )
    )
    if not users:
        return []

    rows = {
        item.user_id: item
        for item in db.scalars(
            select(UserAttendancePresence).where(
                UserAttendancePresence.empresa_id == empresa_id,
                UserAttendancePresence.user_id.in_([user.id for user in users]),
            )
        )
    }
    return [
        (user, snapshot(rows[user.id]) if user.id in rows else None)
        for user in users
    ]


def distribute_handoff_conversation(
    db: Session,
    *,
    conversation: Conversa,
    reason: str,
) -> dict[str, object]:
    """Distribui um handoff em rodízio somente entre usuários realmente disponíveis.

    O campo ``last_assignment_at`` implementa um round-robin persistente: quem
    recebeu há mais tempo volta para o início da fila. ``FOR UPDATE SKIP LOCKED``
    evita que dois handoffs simultâneos escolham o mesmo usuário quando houver
    outros disponíveis.
    """

    now = _now()
    cutoff = now - timedelta(seconds=PRESENCE_TIMEOUT_SECONDS)
    candidates = list(
        db.execute(
            select(Usuario, UserAttendancePresence)
            .join(
                UserAttendancePresence,
                UserAttendancePresence.user_id == Usuario.id,
            )
            .where(
                Usuario.empresa_id == conversation.empresa_id,
                Usuario.ativo.is_(True),
                UserAttendancePresence.empresa_id == conversation.empresa_id,
                UserAttendancePresence.status == STATUS_DISPONIVEL,
                UserAttendancePresence.heartbeat_at.is_not(None),
                UserAttendancePresence.heartbeat_at >= cutoff,
            )
            .order_by(
                UserAttendancePresence.last_assignment_at.asc().nullsfirst(),
                Usuario.id.asc(),
            )
            .with_for_update(skip_locked=True)
        ).all()
    )

    chosen_user: Usuario | None = None
    chosen_presence: UserAttendancePresence | None = None
    for user, presence in candidates:
        if user_module_access(db, user, "CONVERSAS"):
            chosen_user = user
            chosen_presence = presence
            break

    conversation.ia_ativa = False
    if chosen_user is not None and chosen_presence is not None:
        conversation.responsavel_id = chosen_user.id
        conversation.status = StatusConversa.EM_ATENDIMENTO
        chosen_presence.last_assignment_at = now
        chosen_presence.updated_at = now
        notify_user(
            db,
            empresa_id=conversation.empresa_id,
            usuario_id=chosen_user.id,
            titulo="Novo atendimento distribuído",
            mensagem=(
                f"A conversa #{conversation.id} foi encaminhada para você pela IA."
            ),
        )
        assignment: dict[str, object] = {
            "distribuido": True,
            "responsavel_id": chosen_user.id,
            "responsavel_nome": chosen_user.nome,
        }
    else:
        conversation.responsavel_id = None
        conversation.status = StatusConversa.ABERTA
        notify_management(
            db,
            empresa_id=conversation.empresa_id,
            titulo="Atendimento aguardando equipe disponível",
            mensagem=(
                f"A conversa #{conversation.id} foi transferida pela IA, mas não há "
                "ninguém com status Disponível neste momento."
            ),
        )
        assignment = {
            "distribuido": False,
            "responsavel_id": None,
            "responsavel_nome": None,
        }

    db.add(
        Log(
            empresa_id=conversation.empresa_id,
            ator_tipo=AtorLog.SISTEMA,
            ator_id=None,
            acao="DISTRIBUIU_HANDOFF_IA",
            entidade="conversas",
            entidade_id=conversation.id,
            detalhes={
                **assignment,
                "motivo": reason.strip()[:500],
                "politica": "ROUND_ROBIN_DISPONIVEIS",
            },
        )
    )
    db.commit()
    return assignment
