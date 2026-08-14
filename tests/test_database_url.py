from types import SimpleNamespace

from app.database.database import build_connect_args, build_database_url


def _config(**overrides):
    values = {
        "database_url": None,
        "db_host": "localhost",
        "db_port": 5432,
        "db_name": "flowdesk_test",
        "db_user": "postgres",
        "db_password": "secret",
        "db_sslmode": None,
        "sql_echo": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_database_url_remota_normaliza_esquema_postgres() -> None:
    config = _config(
        database_url=(
            "postgres://postgres.projeto:senha@aws-0-sa-east-1.pooler.supabase.com:5432/postgres"
        ),
        db_sslmode="require",
    )

    url = build_database_url(config)

    assert url.drivername == "postgresql+psycopg2"
    assert url.username == "postgres.projeto"
    assert url.password == "senha"
    assert url.host == "aws-0-sa-east-1.pooler.supabase.com"
    assert url.port == 5432
    assert url.database == "postgres"
    assert build_connect_args(config) == {"sslmode": "require"}


def test_database_url_local_mantem_configuracao_separada() -> None:
    config = _config()

    url = build_database_url(config)

    assert url.drivername == "postgresql+psycopg2"
    assert url.username == "postgres"
    assert url.password == "secret"
    assert url.host == "localhost"
    assert url.port == 5432
    assert url.database == "flowdesk_test"
    assert build_connect_args(config) == {}
