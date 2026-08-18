from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.database import get_db
from app.models.models import Usuario
from app.services.attendance_presence import (
    STATUS_AUSENTE,
    STATUS_DISPONIVEL,
    STATUS_OFFLINE,
    get_presence_snapshot,
    set_presence_status,
    team_presence,
    touch_heartbeat,
)


router = APIRouter(prefix="/atendimento-equipe", tags=["Presença de atendimento"])

AttendanceStatus = Literal["DISPONIVEL", "AUSENTE", "OFFLINE"]


class PresenceUpdate(BaseModel):
    status: AttendanceStatus


class PresenceOut(BaseModel):
    user_id: int
    empresa_id: int
    status: AttendanceStatus
    status_efetivo: AttendanceStatus
    heartbeat_at: datetime | None
    last_assignment_at: datetime | None


class TeamPresenceOut(BaseModel):
    user_id: int
    nome: str
    cargo: str
    status: AttendanceStatus
    status_efetivo: AttendanceStatus
    heartbeat_at: datetime | None


def _presence_out(value) -> PresenceOut:
    return PresenceOut(
        user_id=value.user_id,
        empresa_id=value.empresa_id,
        status=value.status,
        status_efetivo=value.effective_status,
        heartbeat_at=value.heartbeat_at,
        last_assignment_at=value.last_assignment_at,
    )


@router.get("/me", response_model=PresenceOut)
def minha_presenca(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PresenceOut:
    return _presence_out(get_presence_snapshot(db, current_user, touch=True))


@router.patch("/me", response_model=PresenceOut)
def atualizar_minha_presenca(
    data: PresenceUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PresenceOut:
    return _presence_out(set_presence_status(db, current_user, data.status))


@router.post("/heartbeat", response_model=PresenceOut)
def heartbeat(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PresenceOut:
    return _presence_out(touch_heartbeat(db, current_user))


@router.get("/equipe", response_model=list[TeamPresenceOut])
def presenca_da_equipe(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TeamPresenceOut]:
    output: list[TeamPresenceOut] = []
    for user, presence in team_presence(db, empresa_id=current_user.empresa_id):
        if presence is None:
            raw = STATUS_OFFLINE
            effective = STATUS_OFFLINE
            heartbeat_at = None
        else:
            raw = presence.status
            effective = presence.effective_status
            heartbeat_at = presence.heartbeat_at
        output.append(
            TeamPresenceOut(
                user_id=user.id,
                nome=user.nome,
                cargo=user.cargo.value,
                status=raw if raw in {STATUS_DISPONIVEL, STATUS_AUSENTE, STATUS_OFFLINE} else STATUS_OFFLINE,
                status_efetivo=(
                    effective
                    if effective in {STATUS_DISPONIVEL, STATUS_AUSENTE, STATUS_OFFLINE}
                    else STATUS_OFFLINE
                ),
                heartbeat_at=heartbeat_at,
            )
        )
    return output
