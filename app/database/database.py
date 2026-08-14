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


DATABASE_URL = build_database_url()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
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
