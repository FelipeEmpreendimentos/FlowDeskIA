from typing import Any

from sqlalchemy.orm import Session

from app.models.enums import AtorLog
from app.models.models import Log, Usuario


def add_audit_log(
    db: Session,
    *,
    user: Usuario,
    action: str,
    entity: str,
    entity_id: int | None,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        Log(
            empresa_id=user.empresa_id,
            ator_tipo=AtorLog.USUARIO,
            ator_id=user.id,
            acao=action,
            entidade=entity,
            entidade_id=entity_id,
            detalhes=details,
        )
    )
