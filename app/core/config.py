import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_JWT_SECRET = "ALTERE_ESTA_CHAVE_ANTES_DE_PUBLICAR_O_SISTEMA"
PRODUCTION_ENVIRONMENTS = {"production", "prod"}


def _required(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or not value.strip():
        raise RuntimeError(
            f"A variável {name} não foi preenchida no arquivo .env."
        )
    return value.strip()


def _boolean(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "sim", "yes", "on"}


def _csv(name: str, default: str) -> list[str]:
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str

    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    sql_echo: bool

    jwt_secret: str
    jwt_algorithm: str
    access_token_minutes: int
    reset_token_minutes: int
    reset_request_cooldown_seconds: int

    frontend_url: str
    smtp_host: str | None
    smtp_port: int
    smtp_user: str | None
    smtp_password: str | None
    smtp_from: str | None
    smtp_from_name: str
    smtp_reply_to: str | None
    smtp_starttls: bool
    smtp_use_ssl: bool
    smtp_timeout_seconds: int

    cors_origins: list[str]

    @property
    def smtp_configured(self) -> bool:
        return bool(
            self.smtp_host
            and self.smtp_user
            and self.smtp_password
            and self.smtp_from
        )


settings = Settings(
    app_name=os.getenv("APP_NAME", "FlowDeskIA"),
    environment=os.getenv("APP_ENV", "development").strip().lower(),
    db_host=_required("DB_HOST", "localhost"),
    db_port=int(_required("DB_PORT", "5432")),
    db_name=_required("DB_NAME"),
    db_user=_required("DB_USER", "postgres"),
    db_password=_required("DB_PASSWORD"),
    sql_echo=_boolean("SQL_ECHO", False),
    jwt_secret=_required("JWT_SECRET", DEFAULT_JWT_SECRET),
    jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
    access_token_minutes=int(os.getenv("ACCESS_TOKEN_MINUTES", "480")),
    reset_token_minutes=int(os.getenv("RESET_TOKEN_MINUTES", "30")),
    reset_request_cooldown_seconds=int(
        os.getenv("RESET_REQUEST_COOLDOWN_SECONDS", "60")
    ),
    frontend_url=os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/"),
    smtp_host=os.getenv("SMTP_HOST") or None,
    smtp_port=int(os.getenv("SMTP_PORT", "587")),
    smtp_user=os.getenv("SMTP_USER") or None,
    smtp_password=os.getenv("SMTP_PASSWORD") or None,
    smtp_from=os.getenv("SMTP_FROM") or None,
    smtp_from_name=os.getenv("SMTP_FROM_NAME", "FlowDeskIA"),
    smtp_reply_to=os.getenv("SMTP_REPLY_TO") or None,
    smtp_starttls=_boolean("SMTP_STARTTLS", True),
    smtp_use_ssl=_boolean("SMTP_USE_SSL", False),
    smtp_timeout_seconds=int(os.getenv("SMTP_TIMEOUT_SECONDS", "20")),
    cors_origins=_csv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173",
    ),
)

if settings.smtp_starttls and settings.smtp_use_ssl:
    raise RuntimeError(
        "SMTP_STARTTLS e SMTP_USE_SSL não podem estar ativos ao mesmo tempo."
    )

if settings.environment in PRODUCTION_ENVIRONMENTS:
    if settings.jwt_secret == DEFAULT_JWT_SECRET or len(settings.jwt_secret) < 32:
        raise RuntimeError(
            "JWT_SECRET inseguro para produção. Use uma chave exclusiva com pelo menos 32 caracteres."
        )
    if not settings.cors_origins or "*" in settings.cors_origins:
        raise RuntimeError(
            "CORS_ORIGINS precisa conter somente os domínios reais do frontend em produção."
        )
    if not settings.frontend_url.startswith("https://"):
        raise RuntimeError(
            "FRONTEND_URL precisa usar HTTPS em produção."
        )
