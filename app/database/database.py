from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from time import sleep
from typing import Protocol

from sqlalchemy import create_engine, text
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

# O dashboard pode abrir várias rotas simultaneamente. Em PostgreSQL direto,
# mantemos dez conexões estáveis e permitimos até cinco conexões temporárias
# para absorver picos curtos sem colocar requisições na fila por vários segundos.
# Em poolers do Supabase evitamos overflow cliente para respeitar o pool externo.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=not IS_SUPABASE_POOLER,
    pool_recycle=1800,
    pool_size=10,
    max_overflow=0 if IS_SUPABASE_POOLER else 5,
    pool_timeout=5,
    pool_use_lifo=not IS_SUPABASE_TRANSACTION_POOLER,
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


def warm_database_pool(connections: int | None = None) -> int:
    """Abre conexões do pool antes da primeira requisição do usuário."""
    target = connections or (10 if IS_SUPABASE_TRANSACTION_POOLER else 5)
    target = max(1, target)

    def warm_one(_: int) -> None:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            # Segura brevemente o checkout para preencher conexões distintas.
            sleep(0.05)

    with ThreadPoolExecutor(max_workers=target) as executor:
        list(executor.map(warm_one, range(target)))

    return target


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
