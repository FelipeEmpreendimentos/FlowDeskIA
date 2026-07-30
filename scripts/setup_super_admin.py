import argparse
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, text

from app.core.security import hash_password
from app.database.database import SessionLocal, engine
from app.models.models import Empresa, Plano
from app.models.platform import (
    EmpresaPlataforma,
    PlanoConfiguracao,
    SuperAdmin,
)


DDL = """
CREATE TABLE IF NOT EXISTS plano_configuracoes (
    plano_id BIGINT PRIMARY KEY REFERENCES planos(id) ON DELETE CASCADE,
    codigo VARCHAR(40) NOT NULL UNIQUE,
    preco_anual NUMERIC(10,2),
    periodo_teste_dias INTEGER NOT NULL DEFAULT 14,
    limite_usuarios INTEGER,
    limite_clientes INTEGER,
    limite_agendamentos_mes INTEGER,
    limite_conversas_mes INTEGER,
    limite_mensagens_ia_mes INTEGER,
    limite_canais INTEGER,
    limite_armazenamento_mb INTEGER,
    ia_incluida BOOLEAN NOT NULL DEFAULT FALSE,
    ia_adicional_disponivel BOOLEAN NOT NULL DEFAULT TRUE,
    recursos JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS empresa_plataforma (
    empresa_id BIGINT PRIMARY KEY REFERENCES empresas(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'TRIAL',
    trial_fim DATE,
    recursos_personalizados JSONB NOT NULL DEFAULT '{}'::jsonb,
    limites_personalizados JSONB NOT NULL DEFAULT '{}'::jsonb,
    ia_adicional_ativo BOOLEAN NOT NULL DEFAULT FALSE,
    ia_limite_adicional INTEGER NOT NULL DEFAULT 0,
    observacoes TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_empresa_plataforma_status
        CHECK (status IN ('TRIAL', 'ATIVA', 'SUSPENSA', 'CANCELADA', 'ARQUIVADA'))
);

CREATE TABLE IF NOT EXISTS super_admins (
    id BIGSERIAL PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    senha_hash VARCHAR(255) NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    dois_fatores_ativo BOOLEAN NOT NULL DEFAULT FALSE,
    ultimo_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS super_admin_logs (
    id BIGSERIAL PRIMARY KEY,
    super_admin_id BIGINT REFERENCES super_admins(id) ON DELETE SET NULL,
    empresa_id BIGINT REFERENCES empresas(id) ON DELETE SET NULL,
    acao VARCHAR(100) NOT NULL,
    entidade VARCHAR(60),
    entidade_id BIGINT,
    dados_anteriores JSONB,
    dados_novos JSONB,
    ip VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_super_admin_logs_created_at
    ON super_admin_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_super_admin_logs_empresa_id
    ON super_admin_logs(empresa_id);

INSERT INTO empresa_plataforma (empresa_id, status)
SELECT id, CASE WHEN ativo THEN 'ATIVA' ELSE 'SUSPENSA' END
FROM empresas
ON CONFLICT (empresa_id) DO NOTHING;
"""


PLANOS_PADRAO = [
    {
        "codigo": "ESSENCIAL",
        "nome": "Essencial",
        "descricao": "Organização da operação para empresas pequenas.",
        "preco": Decimal("0.00"),
        "preco_anual": None,
        "periodo_teste_dias": 14,
        "limite_usuarios": 3,
        "limite_clientes": 500,
        "limite_agendamentos_mes": 500,
        "limite_conversas_mes": 300,
        "limite_mensagens_ia_mes": 0,
        "limite_canais": 1,
        "limite_armazenamento_mb": 1024,
        "ia_incluida": False,
        "ia_adicional_disponivel": True,
        "recursos": {
            "AGENDA": True,
            "CLIENTES": True,
            "VEICULOS": True,
            "SERVICOS": True,
            "CONVERSAS": True,
            "NOTIFICACOES": True,
            "WHATSAPP": False,
            "INSTAGRAM": False,
            "INTELIGENCIA_ARTIFICIAL": False,
            "AVALIACOES": False,
            "RELATORIOS": False,
            "AUTOMACOES": False,
            "MULTIPLAS_UNIDADES": False,
            "SUPORTE_PRIORITARIO": False,
        },
    },
    {
        "codigo": "PROFISSIONAL",
        "nome": "Profissional",
        "descricao": "Gestão completa para empresas com equipe e maior volume.",
        "preco": Decimal("0.00"),
        "preco_anual": None,
        "periodo_teste_dias": 14,
        "limite_usuarios": 10,
        "limite_clientes": 3000,
        "limite_agendamentos_mes": 3000,
        "limite_conversas_mes": 2000,
        "limite_mensagens_ia_mes": 0,
        "limite_canais": 2,
        "limite_armazenamento_mb": 5120,
        "ia_incluida": False,
        "ia_adicional_disponivel": True,
        "recursos": {
            "AGENDA": True,
            "CLIENTES": True,
            "VEICULOS": True,
            "SERVICOS": True,
            "CONVERSAS": True,
            "NOTIFICACOES": True,
            "WHATSAPP": True,
            "INSTAGRAM": True,
            "INTELIGENCIA_ARTIFICIAL": False,
            "AVALIACOES": True,
            "RELATORIOS": True,
            "AUTOMACOES": True,
            "MULTIPLAS_UNIDADES": False,
            "SUPORTE_PRIORITARIO": False,
        },
    },
    {
        "codigo": "INTELIGENTE",
        "nome": "Inteligente",
        "descricao": "Atendimento automatizado com IA e recursos avançados.",
        "preco": Decimal("0.00"),
        "preco_anual": None,
        "periodo_teste_dias": 14,
        "limite_usuarios": 20,
        "limite_clientes": 10000,
        "limite_agendamentos_mes": None,
        "limite_conversas_mes": None,
        "limite_mensagens_ia_mes": 5000,
        "limite_canais": 3,
        "limite_armazenamento_mb": 10240,
        "ia_incluida": True,
        "ia_adicional_disponivel": True,
        "recursos": {
            "AGENDA": True,
            "CLIENTES": True,
            "VEICULOS": True,
            "SERVICOS": True,
            "CONVERSAS": True,
            "NOTIFICACOES": True,
            "WHATSAPP": True,
            "INSTAGRAM": True,
            "INTELIGENCIA_ARTIFICIAL": True,
            "AVALIACOES": True,
            "RELATORIOS": True,
            "AUTOMACOES": True,
            "MULTIPLAS_UNIDADES": False,
            "SUPORTE_PRIORITARIO": True,
        },
    },
    {
        "codigo": "PERSONALIZADO",
        "nome": "Personalizado",
        "descricao": "Limites, recursos e preço negociados individualmente.",
        "preco": Decimal("0.00"),
        "preco_anual": None,
        "periodo_teste_dias": 14,
        "limite_usuarios": None,
        "limite_clientes": None,
        "limite_agendamentos_mes": None,
        "limite_conversas_mes": None,
        "limite_mensagens_ia_mes": None,
        "limite_canais": None,
        "limite_armazenamento_mb": None,
        "ia_incluida": True,
        "ia_adicional_disponivel": True,
        "recursos": {
            "AGENDA": True,
            "CLIENTES": True,
            "VEICULOS": True,
            "SERVICOS": True,
            "CONVERSAS": True,
            "NOTIFICACOES": True,
            "WHATSAPP": True,
            "INSTAGRAM": True,
            "INTELIGENCIA_ARTIFICIAL": True,
            "AVALIACOES": True,
            "RELATORIOS": True,
            "AUTOMACOES": True,
            "MULTIPLAS_UNIDADES": True,
            "SUPORTE_PRIORITARIO": True,
        },
    },
]


def aplicar_estrutura() -> None:
    with engine.begin() as connection:
        connection.execute(text(DDL))


def criar_planos_padrao() -> None:
    db = SessionLocal()
    try:
        for defaults in PLANOS_PADRAO:
            config = db.scalar(
                select(PlanoConfiguracao).where(
                    PlanoConfiguracao.codigo == defaults["codigo"]
                )
            )
            if config is not None:
                continue

            plan = db.scalar(select(Plano).where(Plano.nome == defaults["nome"]))
            if plan is None:
                plan = Plano(
                    nome=defaults["nome"],
                    descricao=defaults["descricao"],
                    preco=defaults["preco"],
                    ativo=True,
                )
                db.add(plan)
                db.flush()

            config = PlanoConfiguracao(
                plano_id=plan.id,
                codigo=defaults["codigo"],
                preco_anual=defaults["preco_anual"],
                periodo_teste_dias=defaults["periodo_teste_dias"],
                limite_usuarios=defaults["limite_usuarios"],
                limite_clientes=defaults["limite_clientes"],
                limite_agendamentos_mes=defaults["limite_agendamentos_mes"],
                limite_conversas_mes=defaults["limite_conversas_mes"],
                limite_mensagens_ia_mes=defaults["limite_mensagens_ia_mes"],
                limite_canais=defaults["limite_canais"],
                limite_armazenamento_mb=defaults["limite_armazenamento_mb"],
                ia_incluida=defaults["ia_incluida"],
                ia_adicional_disponivel=defaults["ia_adicional_disponivel"],
                recursos=defaults["recursos"],
            )
            db.add(config)

        db.commit()
    finally:
        db.close()


def sincronizar_empresas_existentes() -> None:
    db = SessionLocal()
    try:
        companies = list(db.scalars(select(Empresa)))
        for company in companies:
            if db.get(EmpresaPlataforma, company.id) is None:
                db.add(
                    EmpresaPlataforma(
                        empresa_id=company.id,
                        status="ATIVA" if company.ativo else "SUSPENSA",
                        recursos_personalizados={},
                        limites_personalizados={},
                    )
                )
        db.commit()
    finally:
        db.close()


def criar_super_admin(
    *,
    nome: str,
    email: str,
    senha: str,
    atualizar_senha: bool,
) -> None:
    if len(senha) < 8:
        raise SystemExit("A senha precisa ter pelo menos 8 caracteres.")

    db = SessionLocal()
    try:
        normalized_email = email.strip().lower()
        existing = db.scalar(
            select(SuperAdmin).where(SuperAdmin.email == normalized_email)
        )
        if existing is not None:
            if not atualizar_senha:
                print("A conta de Super Admin já existe. Nenhuma senha foi alterada.")
                return
            existing.nome = nome.strip()
            existing.senha_hash = hash_password(senha)
            existing.ativo = True
            db.commit()
            print("Conta de Super Admin atualizada com sucesso.")
            return

        item = SuperAdmin(
            nome=nome.strip(),
            email=normalized_email,
            senha_hash=hash_password(senha),
            ativo=True,
        )
        db.add(item)
        db.commit()
        print("Conta de Super Admin criada com sucesso.")
        print(f"E-mail: {normalized_email}")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepara o Super Admin e os planos padrão do FlowDeskIA."
    )
    parser.add_argument("--nome", help="Nome do primeiro Super Admin")
    parser.add_argument("--email", help="E-mail do primeiro Super Admin")
    parser.add_argument("--senha", help="Senha inicial, mínimo 8 caracteres")
    parser.add_argument(
        "--atualizar-senha",
        action="store_true",
        help="Atualiza a senha caso a conta já exista",
    )
    args = parser.parse_args()

    supplied = [args.nome, args.email, args.senha]
    if any(supplied) and not all(supplied):
        raise SystemExit("Informe --nome, --email e --senha juntos.")

    aplicar_estrutura()
    criar_planos_padrao()
    sincronizar_empresas_existentes()

    if all(supplied):
        criar_super_admin(
            nome=args.nome,
            email=args.email,
            senha=args.senha,
            atualizar_senha=args.atualizar_senha,
        )

    print("Estrutura do Super Admin preparada.")
    print("Planos padrão disponíveis: Essencial, Profissional, Inteligente e Personalizado.")
    print("Período de teste padrão: 14 dias.")


if __name__ == "__main__":
    main()
