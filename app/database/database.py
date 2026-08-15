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
    db_pooler_port_override: int | None
    sql_echo: bool


def _normalize_database_url(raw_url: str) -> URL:
    value = raw_url.strip()
    if value.startswith("postgres://"):
        value = "postgresql+psycopg2://" + value.removeprefix("postgres://")
    elif value.startswith("postgresql://"):
        value = "postgresql+psycopg2://" + value.removeprefix("postgresql://")
    return make_url(value)


def _apply_pooler_port_override(url: URL, config: DatabaseSettings) -> URL:
    override = getattr(config, "db_pooler_port_override", None)
    host = (url.host or "").lower()
    if override and host.endswith(".pooler.supabase.com"):
        return url.set(port=override)
    return url


def build_database_url(config: DatabaseSettings = settings) -> URL:
    if config.database_url:
        url = _normalize_database_url(config.database_url)
        return _apply_pooler_port_override(url, config)

    url = URL.create(
        drivername="postgresql+psycopg2",
        username=config.db_user,
        password=config.db_password,
        host=config.db_host,
        port=config.db_port,
        database=config.db_name,
    )
    return _apply_pooler_port_override(url, config)


def build_connect_args(config: DatabaseSettings = settings) -> dict[str, str]:
    if not config.db_sslmode:
        return {}
    return {"sslmode": config.db_sslmode}


def _is_supabase_pooler(url: URL) -> bool:
    host = (url.host or "").lower()
    return host.endswith(".pooler.supabase.com")


def _is_supabase_transaction_pooler(url: URL) -> bool:
    return _is_supabase_pooler(url) and (url.port or 5432) == 6543


DATABASE_URL = build_database_url()
IS_SUPABASE_POOLER = _is_supabase_pooler(DATABASE_URL)
IS_SUPABASE_TRANSACTION_POOLER = _is_supabase_transaction_pooler(DATABASE_URL)

# O shared pooler do Supabase deve concentrar o pooling de conexões com o
# Postgres. No modo Session (5432), cada conexão cliente reserva uma sessão
# no banco, então limitamos agressivamente o QueuePool local. No modo
# Transaction (6543), as conexões cliente podem ser reutilizadas entre
# transações e o Supavisor absorve a concorrência; por isso permitimos um
# pool local maior para não bloquear as várias chamadas paralelas da UI.
#
# Evitamos pool_pre_ping em ambos os modos do Supabase porque ele acrescenta
# um round trip de rede a cada checkout. pool_recycle mantém as conexões
# cliente renovadas periodicamente sem pagar esse custo em toda requisição.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=not IS_SUPABASE_POOLER,
    pool_recycle=300 if IS_SUPABASE_POOLER else 1800,
    pool_size=10 if IS_SUPABASE_TRANSACTION_POOLER else 5,
    max_overflow=10 if IS_SUPABASE_TRANSACTION_POOLER else 0,
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
