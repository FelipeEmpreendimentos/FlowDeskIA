from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.api.routes.conversas import _requests_human_handoff
from app.services.attendance_presence import (
    STATUS_AUSENTE,
    STATUS_DISPONIVEL,
    STATUS_OFFLINE,
    effective_status,
)


def _presence(status: str, heartbeat_at: datetime | None):
    return SimpleNamespace(status=status, heartbeat_at=heartbeat_at)


def test_online_stays_effectively_online_with_recent_heartbeat() -> None:
    now = datetime.now(timezone.utc)
    assert effective_status(_presence(STATUS_DISPONIVEL, now), now=now) == STATUS_DISPONIVEL


def test_away_stays_away_with_recent_heartbeat() -> None:
    now = datetime.now(timezone.utc)
    assert effective_status(_presence(STATUS_AUSENTE, now), now=now) == STATUS_AUSENTE


def test_offline_is_always_offline() -> None:
    now = datetime.now(timezone.utc)
    assert effective_status(_presence(STATUS_OFFLINE, now), now=now) == STATUS_OFFLINE


def test_stale_presence_becomes_effectively_offline() -> None:
    now = datetime.now(timezone.utc)
    stale = now - timedelta(minutes=3)
    assert effective_status(_presence(STATUS_DISPONIVEL, stale), now=now) == STATUS_OFFLINE
    assert effective_status(_presence(STATUS_AUSENTE, stale), now=now) == STATUS_OFFLINE


def test_explicit_human_requests_are_detected() -> None:
    assert _requests_human_handoff("humano")
    assert _requests_human_handoff("Quero falar com um atendente")
    assert _requests_human_handoff("Me passa pro atendente")
    assert _requests_human_handoff("ATENDIMENTO HUMANO")
    assert _requests_human_handoff("Quero falar com o gerente")


def test_negative_human_request_is_not_transferred() -> None:
    assert not _requests_human_handoff("Não quero falar com atendente")
    assert not _requests_human_handoff("Não preciso de atendente, pode continuar")
