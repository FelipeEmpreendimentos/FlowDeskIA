from sqlalchemy import text

from app.database.database import engine


DDL = """
CREATE TABLE IF NOT EXISTS servico_funcionarios (
    empresa_id BIGINT NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    servico_id BIGINT NOT NULL REFERENCES servicos(id) ON DELETE CASCADE,
    funcionario_id BIGINT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (servico_id, funcionario_id)
);

CREATE INDEX IF NOT EXISTS ix_servico_funcionarios_empresa_servico
    ON servico_funcionarios (empresa_id, servico_id);

CREATE INDEX IF NOT EXISTS ix_servico_funcionarios_empresa_funcionario
    ON servico_funcionarios (empresa_id, funcionario_id);

-- Mantém compatibilidade com empresas que já utilizavam a Agenda antes desta
-- regra: todos os serviços atuais começam habilitados para todos os usuários
-- ativos da mesma empresa. Depois o administrador pode restringir a equipe.
INSERT INTO servico_funcionarios (empresa_id, servico_id, funcionario_id)
SELECT s.empresa_id, s.id, u.id
FROM servicos s
JOIN usuarios u
  ON u.empresa_id = s.empresa_id
 AND u.ativo = TRUE
ON CONFLICT (servico_id, funcionario_id) DO NOTHING;
"""


def aplicar_estrutura() -> None:
    with engine.begin() as connection:
        connection.execute(text(DDL))


if __name__ == "__main__":
    aplicar_estrutura()
    print("Vínculos entre serviços e funcionários preparados com sucesso.")
