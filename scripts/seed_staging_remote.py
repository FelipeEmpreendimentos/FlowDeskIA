"""Seed idempotente usado somente para preparar um banco remoto vazio de staging.

A senha em texto nunca fica no repositório; somente o hash Argon2 forte.
Remover este arquivo depois da primeira migração concluída.
"""

from sqlalchemy import select

from app.database.database import SessionLocal
from app.models.enums import CargoUsuario
from app.models.models import Empresa, Usuario
from app.services.db_utils import commit_or_conflict


EMPRESA_NOME = "LavaHome"
EMPRESA_CNPJ = "00000000000000"
ADMIN_NOME = "Usuário Teste"
ADMIN_EMAIL = "usuarioteste@gmail.com"
ADMIN_PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$FOpDVDi03gAbctQg9osNQw$D7ksmk3iDPmnKRiSLXTjSOKw/wCYat5tZloLifB1oYs"


def main() -> None:
    db = SessionLocal()
    try:
        empresa = db.scalar(select(Empresa).where(Empresa.cnpj == EMPRESA_CNPJ))
        if empresa is None:
            empresa = Empresa(nome=EMPRESA_NOME, cnpj=EMPRESA_CNPJ)
            db.add(empresa)
            db.flush()

        admin = db.scalar(
            select(Usuario).where(
                Usuario.empresa_id == empresa.id,
                Usuario.email == ADMIN_EMAIL,
            )
        )
        if admin is None:
            admin = Usuario(
                empresa_id=empresa.id,
                nome=ADMIN_NOME,
                email=ADMIN_EMAIL,
                senha_hash=ADMIN_PASSWORD_HASH,
                cargo=CargoUsuario.ADMIN,
                ativo=True,
            )
            db.add(admin)
            commit_or_conflict(db, admin)
            print("Seed de staging criado.")
        else:
            print("Seed de staging já existe; nenhuma alteração necessária.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
