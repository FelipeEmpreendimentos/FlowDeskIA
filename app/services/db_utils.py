from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def apply_patch(instance: Any, data: dict[str, Any]) -> Any:
    for field, value in data.items():
        setattr(instance, field, value)
    return instance


def commit_or_conflict(
    db: Session,
    instance: Any | None = None,
    message: str = "Não foi possível salvar. Verifique dados duplicados ou relacionamentos.",
) -> Any | None:
    try:
        db.commit()
        if instance is not None:
            db.refresh(instance)
        return instance
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=message,
        ) from exc
