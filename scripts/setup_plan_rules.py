from sqlalchemy import text

from app.database.database import engine


SQL = """
UPDATE plano_configuracoes
SET ia_incluida = FALSE,
    updated_at = NOW()
WHERE codigo IN ('ESSENCIAL', 'PROFISSIONAL')
  AND ia_incluida IS TRUE;
"""


def aplicar_regras() -> None:
    with engine.begin() as connection:
        connection.execute(text(SQL))


if __name__ == "__main__":
    aplicar_regras()
    print("Regras comerciais dos planos aplicadas com sucesso.")
