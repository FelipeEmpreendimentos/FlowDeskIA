from sqlalchemy import text

from app.database.database import engine


DDL = """
CREATE TABLE IF NOT EXISTS ai_company_settings (
    empresa_id BIGINT PRIMARY KEY REFERENCES empresas(id) ON DELETE CASCADE,
    saudacao_cliente_novo TEXT,
    saudacao_cliente_conhecido TEXT,
    mensagem_transferencia TEXT,
    mensagem_fora_escopo TEXT,
    mensagem_indisponibilidade TEXT,
    mensagem_despedida TEXT,
    texto_menu_principal TEXT,
    tom VARCHAR(20) NOT NULL DEFAULT 'EQUILIBRADO',
    tamanho_resposta VARCHAR(20) NOT NULL DEFAULT 'CURTA',
    usar_emojis BOOLEAN NOT NULL DEFAULT TRUE,
    criar_cliente_auto BOOLEAN NOT NULL DEFAULT TRUE,
    criar_veiculo_auto BOOLEAN NOT NULL DEFAULT TRUE,
    pode_agendar BOOLEAN NOT NULL DEFAULT TRUE,
    pode_reagendar BOOLEAN NOT NULL DEFAULT TRUE,
    pode_cancelar BOOLEAN NOT NULL DEFAULT TRUE,
    confirmar_acoes BOOLEAN NOT NULL DEFAULT TRUE,
    transferir_fora_escopo BOOLEAN NOT NULL DEFAULT TRUE,
    fluxo_guiado_ativo BOOLEAN NOT NULL DEFAULT TRUE,
    mostrar_interpretacao BOOLEAN NOT NULL DEFAULT TRUE,
    tentativas_antes_handoff SMALLINT NOT NULL DEFAULT 2,
    campos_cliente_obrigatorios JSONB NOT NULL DEFAULT '["nome"]'::jsonb,
    campos_veiculo_obrigatorios JSONB NOT NULL DEFAULT '["tipo_veiculo"]'::jsonb,
    conhecimento JSONB NOT NULL DEFAULT '[]'::jsonb,
    menu_principal JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_ai_settings_tom CHECK (tom IN ('FORMAL', 'EQUILIBRADO', 'INFORMAL')),
    CONSTRAINT ck_ai_settings_tamanho CHECK (tamanho_resposta IN ('CURTA', 'MEDIA', 'DETALHADA')),
    CONSTRAINT ck_ai_settings_handoff CHECK (tentativas_antes_handoff BETWEEN 1 AND 5)
);

ALTER TABLE ai_company_settings ADD COLUMN IF NOT EXISTS texto_menu_principal TEXT;
ALTER TABLE ai_company_settings ADD COLUMN IF NOT EXISTS fluxo_guiado_ativo BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE ai_company_settings ADD COLUMN IF NOT EXISTS mostrar_interpretacao BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE ai_company_settings ADD COLUMN IF NOT EXISTS menu_principal JSONB NOT NULL DEFAULT '[]'::jsonb;

CREATE TABLE IF NOT EXISTS ai_contact_metadata (
    cliente_id BIGINT PRIMARY KEY REFERENCES clientes(id) ON DELETE CASCADE,
    empresa_id BIGINT NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    criado_por_ia BOOLEAN NOT NULL DEFAULT TRUE,
    origem VARCHAR(40) NOT NULL DEFAULT 'IA',
    cadastro_completo BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ai_contact_metadata_empresa
    ON ai_contact_metadata(empresa_id, created_at DESC);

CREATE TABLE IF NOT EXISTS ai_vehicle_metadata (
    veiculo_id BIGINT PRIMARY KEY REFERENCES veiculos(id) ON DELETE CASCADE,
    empresa_id BIGINT NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    criado_por_ia BOOLEAN NOT NULL DEFAULT TRUE,
    origem VARCHAR(40) NOT NULL DEFAULT 'IA',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ai_vehicle_metadata_empresa
    ON ai_vehicle_metadata(empresa_id, created_at DESC);

CREATE TABLE IF NOT EXISTS ai_atendimento_sessoes (
    id BIGSERIAL PRIMARY KEY,
    empresa_id BIGINT NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    canal VARCHAR(30) NOT NULL DEFAULT 'WHATSAPP',
    external_id VARCHAR(150) NOT NULL,
    cliente_id BIGINT REFERENCES clientes(id) ON DELETE SET NULL,
    estado VARCHAR(30) NOT NULL DEFAULT 'ATENDENDO',
    falhas_entendimento SMALLINT NOT NULL DEFAULT 0,
    pending_action JSONB,
    flow_context JSONB,
    last_intent VARCHAR(80),
    last_tool_trace JSONB NOT NULL DEFAULT '[]'::jsonb,
    handoff_motivo TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ai_atendimento_empresa_canal_external
        UNIQUE (empresa_id, canal, external_id),
    CONSTRAINT ck_ai_atendimento_falhas CHECK (falhas_entendimento >= 0)
);
ALTER TABLE ai_atendimento_sessoes ADD COLUMN IF NOT EXISTS flow_context JSONB;
CREATE INDEX IF NOT EXISTS idx_ai_atendimento_cliente
    ON ai_atendimento_sessoes(empresa_id, cliente_id, updated_at DESC);

INSERT INTO ai_company_settings (empresa_id)
SELECT id FROM empresas
ON CONFLICT (empresa_id) DO NOTHING;
"""


def aplicar_estrutura() -> None:
    with engine.begin() as connection:
        connection.execute(text(DDL))


if __name__ == "__main__":
    aplicar_estrutura()
    print("Estrutura da IA v2 preparada com sucesso.")
