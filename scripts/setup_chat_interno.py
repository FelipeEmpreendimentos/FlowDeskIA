from sqlalchemy import text

from app.database.database import engine


DDL = """
-- Estrutura legada mantida apenas para migrar mensagens criadas antes dos canais.
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

CREATE TABLE IF NOT EXISTS canais_chat_interno (
    id BIGSERIAL PRIMARY KEY,
    empresa_id BIGINT NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    tipo VARCHAR(10) NOT NULL,
    nome VARCHAR(100),
    criado_por_id BIGINT REFERENCES usuarios(id) ON DELETE SET NULL,
    chave_unica VARCHAR(160) UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_canal_chat_interno_tipo
        CHECK (tipo IN ('GERAL', 'DIRETO', 'GRUPO'))
);

CREATE TABLE IF NOT EXISTS membros_canais_chat_interno (
    id BIGSERIAL PRIMARY KEY,
    canal_id BIGINT NOT NULL REFERENCES canais_chat_interno(id) ON DELETE CASCADE,
    usuario_id BIGINT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_membro_canal_chat_interno UNIQUE (canal_id, usuario_id)
);

CREATE TABLE IF NOT EXISTS mensagens_canais_chat_interno (
    id BIGSERIAL PRIMARY KEY,
    canal_id BIGINT NOT NULL REFERENCES canais_chat_interno(id) ON DELETE CASCADE,
    empresa_id BIGINT NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    usuario_id BIGINT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    conteudo TEXT NOT NULL,
    legacy_mensagem_id BIGINT UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_mensagem_canal_chat_interno_conteudo
        CHECK (char_length(trim(conteudo)) BETWEEN 1 AND 2000)
);

CREATE TABLE IF NOT EXISTS leituras_canais_chat_interno (
    id BIGSERIAL PRIMARY KEY,
    canal_id BIGINT NOT NULL REFERENCES canais_chat_interno(id) ON DELETE CASCADE,
    empresa_id BIGINT NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    usuario_id BIGINT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    ultima_mensagem_id BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_leitura_canal_chat_interno_usuario
        UNIQUE (canal_id, usuario_id)
);

CREATE INDEX IF NOT EXISTS idx_canais_chat_interno_empresa
    ON canais_chat_interno (empresa_id, tipo, id);
CREATE INDEX IF NOT EXISTS idx_membros_chat_interno_usuario
    ON membros_canais_chat_interno (usuario_id, canal_id);
CREATE INDEX IF NOT EXISTS idx_mensagens_canais_chat_interno
    ON mensagens_canais_chat_interno (canal_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_mensagens_canais_chat_empresa
    ON mensagens_canais_chat_interno (empresa_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_leituras_canais_chat_usuario
    ON leituras_canais_chat_interno (empresa_id, usuario_id, canal_id);

INSERT INTO canais_chat_interno (
    empresa_id,
    tipo,
    nome,
    chave_unica
)
SELECT
    empresas.id,
    'GERAL',
    'Geral da empresa',
    'GERAL:' || empresas.id::text
FROM empresas
ON CONFLICT (chave_unica) DO NOTHING;

INSERT INTO mensagens_canais_chat_interno (
    canal_id,
    empresa_id,
    usuario_id,
    conteudo,
    legacy_mensagem_id,
    created_at
)
SELECT
    canais.id,
    mensagens.empresa_id,
    mensagens.usuario_id,
    mensagens.conteudo,
    mensagens.id,
    mensagens.created_at
FROM mensagens_chat_interno AS mensagens
JOIN canais_chat_interno AS canais
    ON canais.empresa_id = mensagens.empresa_id
   AND canais.tipo = 'GERAL'
ON CONFLICT (legacy_mensagem_id) DO NOTHING;

INSERT INTO leituras_canais_chat_interno (
    canal_id,
    empresa_id,
    usuario_id,
    ultima_mensagem_id,
    updated_at
)
SELECT
    canais.id,
    leituras.empresa_id,
    leituras.usuario_id,
    COALESCE((
        SELECT MAX(novas.id)
        FROM mensagens_canais_chat_interno AS novas
        WHERE novas.empresa_id = leituras.empresa_id
          AND novas.legacy_mensagem_id <= leituras.ultima_mensagem_id
    ), 0),
    leituras.updated_at
FROM leituras_chat_interno AS leituras
JOIN canais_chat_interno AS canais
    ON canais.empresa_id = leituras.empresa_id
   AND canais.tipo = 'GERAL'
ON CONFLICT (canal_id, usuario_id) DO NOTHING;
"""


def aplicar_estrutura() -> None:
    with engine.begin() as connection:
        connection.execute(text(DDL))


if __name__ == "__main__":
    aplicar_estrutura()
    print("Chat interno com conversas diretas e grupos preparado com sucesso.")
