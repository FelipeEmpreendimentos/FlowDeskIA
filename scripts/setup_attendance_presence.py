from sqlalchemy import text

from app.database.database import engine


DDL = """
CREATE TABLE IF NOT EXISTS user_attendance_presence (
    user_id BIGINT PRIMARY KEY REFERENCES usuarios(id) ON DELETE CASCADE,
    empresa_id BIGINT NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'OFFLINE',
    heartbeat_at TIMESTAMPTZ,
    last_assignment_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_user_attendance_presence_status
        CHECK (status IN ('DISPONIVEL', 'AUSENTE', 'OFFLINE'))
);
CREATE INDEX IF NOT EXISTS idx_user_attendance_presence_distribution
    ON user_attendance_presence(empresa_id, status, heartbeat_at, last_assignment_at);
"""


def aplicar_estrutura() -> None:
    with engine.begin() as connection:
        connection.execute(text(DDL))


if __name__ == "__main__":
    aplicar_estrutura()
    print("Estrutura de presença da equipe preparada com sucesso.")
