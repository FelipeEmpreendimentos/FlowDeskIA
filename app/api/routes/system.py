from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.database.database import engine

router = APIRouter(prefix="/system", tags=["Sistema"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/database")
def database_health() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "banco": "conectado"}
    except Exception as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Falha ao conectar ao PostgreSQL: {exc}",
        ) from exc
