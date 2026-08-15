"""Índices de leitura para os caminhos mais usados do FlowDeskIA.

O script é idempotente e não altera dados nem regras de negócio. Ele existe
para que staging/produção novos já nasçam com os mesmos índices aplicados ao
banco remoto durante a preparação de performance.
"""

from sqlalchemy import text

from app.database.database import engine


INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_usuarios_empresa_ativo_nome ON usuarios (empresa_id, ativo, nome)",
    "CREATE INDEX IF NOT EXISTS idx_usuarios_empresa_email_ci ON usuarios (empresa_id, lower(email))",
    "CREATE INDEX IF NOT EXISTS idx_clientes_empresa_status_nome ON clientes (empresa_id, status, nome)",
    "CREATE INDEX IF NOT EXISTS idx_clientes_empresa_nome_ci ON clientes (empresa_id, lower(btrim(nome)))",
    "CREATE INDEX IF NOT EXISTS idx_veiculos_cliente_id ON veiculos (cliente_id, id)",
    "CREATE INDEX IF NOT EXISTS idx_servicos_empresa_ativo_nome ON servicos (empresa_id, ativo, nome)",
    "CREATE INDEX IF NOT EXISTS idx_servicos_empresa_nome_ci ON servicos (empresa_id, lower(btrim(nome)))",
    "CREATE INDEX IF NOT EXISTS idx_agendamentos_empresa_data_hora ON agendamentos (empresa_id, data, hora_inicio, id)",
    "CREATE INDEX IF NOT EXISTS idx_agendamentos_empresa_status ON agendamentos (empresa_id, status, id)",
    "CREATE INDEX IF NOT EXISTS idx_agendamentos_empresa_cliente ON agendamentos (empresa_id, cliente_id, id)",
    "CREATE INDEX IF NOT EXISTS idx_agendamentos_empresa_funcionario_data ON agendamentos (empresa_id, funcionario_id, data, hora_inicio)",
    "CREATE INDEX IF NOT EXISTS idx_agendamentos_servico_id ON agendamentos (servico_id, id)",
    "CREATE INDEX IF NOT EXISTS idx_agendamentos_veiculo_id ON agendamentos (veiculo_id, id)",
    "CREATE INDEX IF NOT EXISTS idx_conversas_empresa_status_interacao ON conversas (empresa_id, status, ultima_interacao DESC, id DESC)",
    "CREATE INDEX IF NOT EXISTS idx_conversas_empresa_cliente_status ON conversas (empresa_id, cliente_id, status, id)",
    "CREATE INDEX IF NOT EXISTS idx_conversas_empresa_responsavel_status ON conversas (empresa_id, responsavel_id, status, id)",
    "CREATE INDEX IF NOT EXISTS idx_mensagens_conversa_id ON mensagens (conversa_id, id DESC)",
    "CREATE INDEX IF NOT EXISTS idx_notificacoes_empresa_lida_created ON notificacoes (empresa_id, lida, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_notificacoes_empresa_usuario_lida ON notificacoes (empresa_id, usuario_id, lida, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_horarios_empresa_funcionario_dia ON horarios (empresa_id, funcionario_id, dia_semana, ativo)",
    "CREATE INDEX IF NOT EXISTS idx_bloqueios_empresa_funcionario_datas ON bloqueios_agenda (empresa_id, funcionario_id, data_inicio, data_fim)",
    "CREATE INDEX IF NOT EXISTS idx_integracoes_empresa_ativo ON integracoes (empresa_id, ativo, id)",
)


def aplicar_indices() -> None:
    with engine.begin() as connection:
        for statement in INDEXES:
            connection.execute(text(statement))


if __name__ == "__main__":
    aplicar_indices()
    print("Índices de performance aplicados com sucesso.")
