from sqlalchemy import text

from app.database.database import engine


MODULES = (
    "AGENDA",
    "CHAT_INTERNO",
    "CONVERSAS",
    "CLIENTES",
    "VEICULOS",
    "SERVICOS",
    "FINANCEIRO",
    "RELATORIOS",
    "EQUIPE",
)

DDL = """
CREATE TABLE IF NOT EXISTS empresa_modulos (
    id BIGSERIAL PRIMARY KEY,
    empresa_id BIGINT NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    modulo VARCHAR(40) NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_empresa_modulo UNIQUE (empresa_id, modulo)
);

CREATE TABLE IF NOT EXISTS usuario_permissoes_modulo (
    id BIGSERIAL PRIMARY KEY,
    empresa_id BIGINT NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    usuario_id BIGINT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    modulo VARCHAR(40) NOT NULL,
    permitido BOOLEAN NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_usuario_permissao_modulo UNIQUE (usuario_id, modulo)
);

CREATE INDEX IF NOT EXISTS idx_empresa_modulos_empresa
    ON empresa_modulos (empresa_id, modulo);
CREATE INDEX IF NOT EXISTS idx_usuario_permissoes_empresa
    ON usuario_permissoes_modulo (empresa_id, usuario_id, modulo);
"""


def aplicar_estrutura() -> None:
    with engine.begin() as connection:
        connection.execute(text(DDL))
        for module in MODULES:
            connection.execute(
                text(
                    """
                    INSERT INTO empresa_modulos (empresa_id, modulo, ativo)
                    SELECT id, :module, TRUE
                    FROM empresas
                    ON CONFLICT (empresa_id, modulo) DO NOTHING
                    """
                ),
                {"module": module},
            )


if __name__ == "__main__":
    aplicar_estrutura()
    print("Módulos e permissões preparados com sucesso.")
