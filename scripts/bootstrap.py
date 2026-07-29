import argparse
from sqlalchemy import select

from app.core.security import hash_password
from app.database.database import SessionLocal
from app.models.enums import CargoUsuario
from app.models.models import Empresa, Usuario
from app.services.db_utils import commit_or_conflict


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cria a primeira empresa e o usuário administrador."
    )
    parser.add_argument("--empresa", required=True, help="Nome da empresa")
    parser.add_argument("--cnpj", required=True, help="CNPJ usado no banco")
    parser.add_argument("--nome", required=True, help="Nome do administrador")
    parser.add_argument("--email", required=True, help="E-mail do administrador")
    parser.add_argument("--senha", required=True, help="Senha inicial, mínimo 8 caracteres")
    args = parser.parse_args()

    if len(args.senha) < 8:
        raise SystemExit("A senha precisa ter pelo menos 8 caracteres.")

    db = SessionLocal()
    try:
        empresa = db.scalar(select(Empresa).where(Empresa.cnpj == args.cnpj))
        if empresa is None:
            empresa = Empresa(nome=args.empresa, cnpj=args.cnpj)
            db.add(empresa)
            db.flush()

        existing = db.scalar(
            select(Usuario).where(
                Usuario.empresa_id == empresa.id,
                Usuario.email == args.email,
            )
        )
        if existing is not None:
            raise SystemExit("Esse administrador já existe.")

        admin = Usuario(
            empresa_id=empresa.id,
            nome=args.nome,
            email=args.email,
            senha_hash=hash_password(args.senha),
            cargo=CargoUsuario.ADMIN,
            ativo=True,
        )
        db.add(admin)
        commit_or_conflict(db, admin)

        print("Cadastro inicial concluído.")
        print(f"Empresa ID: {empresa.id}")
        print(f"Usuário ID: {admin.id}")
        print("Use o Empresa ID no campo empresa_id do login.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
