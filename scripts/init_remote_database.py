"""Inicializa um PostgreSQL vazio para staging/producao.

Cria os enums PostgreSQL usados pelos models, cria as tabelas registradas no
SQLAlchemy e, em seguida, aplica os ajustes/backfills idempotentes da release.
"""

from sqlalchemy.dialects.postgresql import ENUM as PGEnum

# Importa todos os modulos de models para registrar as tabelas no metadata.
import app.models.access_control  # noqa: F401
import app.models.agenda_settings  # noqa: F401
import app.models.engagement  # noqa: F401
import app.models.finance  # noqa: F401
import app.models.internal_chat  # noqa: F401
import app.models.models  # noqa: F401
import app.models.platform  # noqa: F401
from app.database.database import Base, engine
from scripts.setup_release import main as setup_release


def postgres_enum_types() -> list[PGEnum]:
    enums: dict[tuple[str | None, str], PGEnum] = {}

    for table in Base.metadata.tables.values():
        for column in table.columns:
            column_type = column.type
            if not isinstance(column_type, PGEnum) or not column_type.name:
                continue
            key = (column_type.schema, column_type.name)
            enums[key] = column_type

    return list(enums.values())


def create_base_schema() -> None:
    if engine.dialect.name != "postgresql":
        raise RuntimeError("A inicializacao remota requer PostgreSQL.")

    with engine.begin() as connection:
        for enum_type in postgres_enum_types():
            PGEnum(
                *enum_type.enums,
                name=enum_type.name,
                schema=enum_type.schema,
                create_type=True,
            ).create(connection, checkfirst=True)

        Base.metadata.create_all(bind=connection, checkfirst=True)


def main() -> None:
    create_base_schema()
    setup_release()
    print("Banco remoto inicializado com sucesso.")


if __name__ == "__main__":
    main()
