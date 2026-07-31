from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.database.database import engine


router = APIRouter(prefix="/system", tags=["Sistema"])


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "verificacao": "liveness",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _verificar_banco() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "banco": "conectado",
            "verificacao": "readiness",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Aplicação temporariamente indisponível.",
        ) from exc


@router.get("/ready")
def readiness() -> dict[str, str]:
    return _verificar_banco()


@router.get("/database", deprecated=True)
def database_health() -> dict[str, str]:
    return _verificar_banco()
