from collections.abc import Generator
from typing import Protocol

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class DatabaseSettings(Protocol):
    database_url: str | None
    db_host: str
    db_port: int
    db_name: str | None
    db_user: str
    db_password: str | None
    db_sslmode: str | None
    sql_echo: bool


def _normalize_database_url(raw_url: str) -> URL:
    value = raw_url.strip()
    if value.startswith("postgres://"):
        value = "postgresql+psycopg2://" + value.removeprefix("postgres://")
    elif value.startswith("postgresql://"):
        value = "postgresql+psycopg2://" + value.removeprefix("postgresql://")
    return make_url(value)


def build_database_url(config: DatabaseSettings = settings) -> URL:
    if config.database_url:
        return _normalize_database_url(config.database_url)

    return URL.create(
        drivername="postgresql+psycopg2",
        username=config.db_user,
        password=config.db_password,
        host=config.db_host,
        port=config.db_port,
        database=config.db_name,
    )


def build_connect_args(config: DatabaseSettings = settings) -> dict[str, str]:
    if not config.db_sslmode:
        return {}
    return {"sslmode": config.db_sslmode}


def _is_supabase_session_pooler(url: URL) -> bool:
    host = (url.host or "").lower()
    return host.endswith(".pooler.supabase.com") and (url.port or 5432) == 5432


DATABASE_URL = build_database_url()
IS_SUPABASE_SESSION_POOLER = _is_supabase_session_pooler(DATABASE_URL)

# O Session Pooler do Supabase reserva uma conexão do Postgres para cada
# conexão cliente. O QueuePool padrão do SQLAlchemy pode chegar a 15
# conexões por processo (5 + 10 de overflow), exatamente o limite observado
# no staging. Durante um deploy blue/green duas instâncias podem coexistir,
# por isso mantemos no máximo 5 por processo e sem overflow.
#
# Também evitamos pool_pre_ping no Session Pooler: ele executa um ping a cada
# checkout e, com API e banco em regiões diferentes, adiciona um round trip
# desnecessário a praticamente toda requisição. O recycle curto limita o
# tempo de vida das conexões mantidas pelo processo.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=not IS_SUPABASE_SESSION_POOLER,
    pool_recycle=300 if IS_SUPABASE_SESSION_POOLER else 1800,
    pool_size=5 if IS_SUPABASE_SESSION_POOLER else 5,
    max_overflow=0 if IS_SUPABASE_SESSION_POOLER else 10,
    pool_timeout=20,
    pool_use_lifo=True,
    connect_args=build_connect_args(),
    echo=settings.sql_echo,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Classe base para os models do SQLAlchemy."""


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
