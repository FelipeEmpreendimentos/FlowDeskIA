from sqlalchemy import text

from app.database.database import engine


DDL = """
CREATE TABLE IF NOT EXISTS configuracoes_relatorios (
    empresa_id BIGINT PRIMARY KEY REFERENCES empresas(id) ON DELETE CASCADE,
    usar_financeiro BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO configuracoes_relatorios (empresa_id, usar_financeiro)
SELECT id, TRUE
FROM empresas
ON CONFLICT (empresa_id) DO NOTHING;
"""


def aplicar_estrutura() -> None:
    with engine.begin() as connection:
        connection.execute(text(DDL))


if __name__ == "__main__":
    aplicar_estrutura()
    print("Configurações dos relatórios atualizadas com sucesso.")
