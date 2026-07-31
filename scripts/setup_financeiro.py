from sqlalchemy import text

from app.database.database import engine


DDL = """
CREATE TABLE IF NOT EXISTS fechamentos_financeiros (
    id BIGSERIAL PRIMARY KEY,
    empresa_id BIGINT NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    agendamento_id BIGINT NOT NULL REFERENCES agendamentos(id) ON DELETE CASCADE,
    valor_original NUMERIC(12,2) NOT NULL,
    desconto_tipo VARCHAR(20),
    desconto_valor NUMERIC(12,2) NOT NULL DEFAULT 0,
    valor_final NUMERIC(12,2) NOT NULL,
    valor_recebido NUMERIC(12,2) NOT NULL DEFAULT 0,
    valor_pendente NUMERIC(12,2) NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDENTE',
    observacoes TEXT,
    fechado_por_id BIGINT REFERENCES usuarios(id) ON DELETE SET NULL,
    atualizado_por_id BIGINT REFERENCES usuarios(id) ON DELETE SET NULL,
    fechado_em TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_fechamento_empresa_agendamento
        UNIQUE (empresa_id, agendamento_id),
    CONSTRAINT ck_fechamento_status
        CHECK (status IN ('PENDENTE', 'PARCIAL', 'PAGO', 'CORTESIA', 'ESTORNADO')),
    CONSTRAINT ck_fechamento_desconto_tipo
        CHECK (desconto_tipo IS NULL OR desconto_tipo IN ('VALOR', 'PERCENTUAL')),
    CONSTRAINT ck_fechamento_valores_nao_negativos
        CHECK (
            valor_original >= 0 AND desconto_valor >= 0 AND valor_final >= 0
            AND valor_recebido >= 0 AND valor_pendente >= 0
        )
);

CREATE TABLE IF NOT EXISTS pagamentos_atendimento (
    id BIGSERIAL PRIMARY KEY,
    empresa_id BIGINT NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    fechamento_id BIGINT NOT NULL REFERENCES fechamentos_financeiros(id) ON DELETE CASCADE,
    forma_pagamento VARCHAR(30) NOT NULL,
    valor NUMERIC(12,2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'CONFIRMADO',
    recebido_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    registrado_por_id BIGINT REFERENCES usuarios(id) ON DELETE SET NULL,
    observacoes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_pagamento_atendimento_status
        CHECK (status IN ('CONFIRMADO', 'ESTORNADO')),
    CONSTRAINT ck_pagamento_atendimento_valor_positivo
        CHECK (valor > 0),
    CONSTRAINT ck_pagamento_atendimento_forma
        CHECK (
            forma_pagamento IN (
                'DINHEIRO', 'PIX', 'CARTAO_DEBITO',
                'CARTAO_CREDITO', 'BOLETO'
            )
        )
);

CREATE INDEX IF NOT EXISTS idx_fechamentos_empresa_status
    ON fechamentos_financeiros (empresa_id, status);
CREATE INDEX IF NOT EXISTS idx_fechamentos_agendamento
    ON fechamentos_financeiros (agendamento_id);
CREATE INDEX IF NOT EXISTS idx_pagamentos_fechamento_status
    ON pagamentos_atendimento (fechamento_id, status);
CREATE INDEX IF NOT EXISTS idx_pagamentos_empresa_recebido
    ON pagamentos_atendimento (empresa_id, recebido_em DESC);

INSERT INTO fechamentos_financeiros (
    empresa_id,
    agendamento_id,
    valor_original,
    valor_final,
    valor_recebido,
    valor_pendente,
    status,
    fechado_em
)
SELECT
    agendamento.empresa_id,
    agendamento.id,
    COALESCE(
        agendamento.valor_final,
        agendamento.valor_base + agendamento.valor_adicional,
        0
    ),
    COALESCE(
        agendamento.valor_final,
        agendamento.valor_base + agendamento.valor_adicional,
        0
    ),
    0,
    COALESCE(
        agendamento.valor_final,
        agendamento.valor_base + agendamento.valor_adicional,
        0
    ),
    'PENDENTE',
    agendamento.finalizado_em
FROM agendamentos AS agendamento
WHERE agendamento.status = 'FINALIZADO'
ON CONFLICT (empresa_id, agendamento_id) DO NOTHING;

CREATE OR REPLACE FUNCTION flowdesk_criar_fechamento_financeiro()
RETURNS TRIGGER AS $$
DECLARE
    total NUMERIC(12,2);
BEGIN
    IF NEW.status <> 'FINALIZADO' THEN
        RETURN NEW;
    END IF;

    IF TG_OP = 'UPDATE' AND OLD.status = 'FINALIZADO' THEN
        RETURN NEW;
    END IF;

    total := COALESCE(
        NEW.valor_final,
        NEW.valor_base + NEW.valor_adicional,
        0
    );

    INSERT INTO fechamentos_financeiros (
        empresa_id,
        agendamento_id,
        valor_original,
        valor_final,
        valor_recebido,
        valor_pendente,
        status,
        fechado_em
    ) VALUES (
        NEW.empresa_id,
        NEW.id,
        total,
        total,
        0,
        total,
        'PENDENTE',
        COALESCE(NEW.finalizado_em, NOW())
    )
    ON CONFLICT (empresa_id, agendamento_id) DO NOTHING;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_agendamento_criar_fechamento ON agendamentos;
CREATE TRIGGER trg_agendamento_criar_fechamento
AFTER INSERT OR UPDATE OF status ON agendamentos
FOR EACH ROW
EXECUTE FUNCTION flowdesk_criar_fechamento_financeiro();
"""


def aplicar_estrutura() -> None:
    with engine.begin() as connection:
        connection.execute(text(DDL))


if __name__ == "__main__":
    aplicar_estrutura()
    print("Estrutura financeira criada ou atualizada com sucesso.")
