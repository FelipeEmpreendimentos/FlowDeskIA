from sqlalchemy import text

from app.database.database import engine


DDL = """
CREATE TABLE IF NOT EXISTS empresa_onboarding (
    id BIGSERIAL PRIMARY KEY,
    empresa_id BIGINT NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    oculto BOOLEAN NOT NULL DEFAULT FALSE,
    concluido_em TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_empresa_onboarding_empresa UNIQUE (empresa_id)
);

CREATE TABLE IF NOT EXISTS preferencias_notificacao (
    id BIGSERIAL PRIMARY KEY,
    empresa_id BIGINT NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    usuario_id BIGINT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    agendamentos BOOLEAN NOT NULL DEFAULT TRUE,
    financeiro BOOLEAN NOT NULL DEFAULT TRUE,
    conversas BOOLEAN NOT NULL DEFAULT TRUE,
    avaliacoes BOOLEAN NOT NULL DEFAULT TRUE,
    integracoes BOOLEAN NOT NULL DEFAULT TRUE,
    planos_limites BOOLEAN NOT NULL DEFAULT TRUE,
    sistema BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_preferencia_notificacao_usuario UNIQUE (usuario_id)
);

CREATE INDEX IF NOT EXISTS idx_empresa_onboarding_empresa
    ON empresa_onboarding (empresa_id);
CREATE INDEX IF NOT EXISTS idx_preferencias_notificacao_empresa
    ON preferencias_notificacao (empresa_id, usuario_id);
"""


def aplicar_estrutura() -> None:
    with engine.begin() as connection:
        connection.execute(text(DDL))


if __name__ == "__main__":
    aplicar_estrutura()
    print("Onboarding e preferências de notificações atualizados com sucesso.")
