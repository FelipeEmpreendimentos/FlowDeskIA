from sqlalchemy import text

from app.database.database import engine


DDL = """
CREATE TABLE IF NOT EXISTS configuracoes_agenda (
    empresa_id BIGINT PRIMARY KEY REFERENCES empresas(id) ON DELETE CASCADE,
    intervalo_minutos INTEGER NOT NULL DEFAULT 30,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_configuracoes_agenda_intervalo
        CHECK (intervalo_minutos IN (15, 30, 60))
);

INSERT INTO configuracoes_agenda (empresa_id, intervalo_minutos)
SELECT id, 30
FROM empresas
ON CONFLICT (empresa_id) DO NOTHING;
"""


def aplicar_estrutura() -> None:
    with engine.begin() as connection:
        connection.execute(text(DDL))


if __name__ == "__main__":
    aplicar_estrutura()
    print("Configurações da agenda atualizadas com sucesso.")
