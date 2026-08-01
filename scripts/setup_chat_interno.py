from sqlalchemy import text

from app.database.database import engine


DDL = """
CREATE TABLE IF NOT EXISTS mensagens_chat_interno (
    id BIGSERIAL PRIMARY KEY,
    empresa_id BIGINT NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    usuario_id BIGINT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    conteudo TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_mensagem_chat_interno_conteudo
        CHECK (char_length(trim(conteudo)) BETWEEN 1 AND 2000)
);

CREATE TABLE IF NOT EXISTS leituras_chat_interno (
    id BIGSERIAL PRIMARY KEY,
    empresa_id BIGINT NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    usuario_id BIGINT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    ultima_mensagem_id BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_leitura_chat_interno_usuario
        UNIQUE (empresa_id, usuario_id)
);

CREATE INDEX IF NOT EXISTS idx_mensagens_chat_interno_empresa_id
    ON mensagens_chat_interno (empresa_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_mensagens_chat_interno_usuario
    ON mensagens_chat_interno (empresa_id, usuario_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_leituras_chat_interno_empresa_usuario
    ON leituras_chat_interno (empresa_id, usuario_id);
"""


def aplicar_estrutura() -> None:
    with engine.begin() as connection:
        connection.execute(text(DDL))


if __name__ == "__main__":
    aplicar_estrutura()
    print("Estrutura do chat interno preparada com sucesso.")
