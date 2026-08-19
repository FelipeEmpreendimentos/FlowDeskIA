import os

from sqlalchemy import func, select

from app.database.database import SessionLocal
from app.models.enums import CargoUsuario
from app.models.models import Usuario


def aplicar_bootstrap() -> bool:
    empresa_raw = os.getenv("BOOTSTRAP_COMPANY_ADMIN_COMPANY_ID", "").strip()
    email = os.getenv("BOOTSTRAP_COMPANY_ADMIN_EMAIL", "").strip().lower()

    if not empresa_raw or not email:
        return False

    empresa_id = int(empresa_raw)
    with SessionLocal() as db:
        usuario = db.scalar(
            select(Usuario).where(
                Usuario.empresa_id == empresa_id,
                func.lower(Usuario.email) == email,
            )
        )
        if usuario is None:
            raise RuntimeError(
                f"Usuário bootstrap não encontrado: empresa={empresa_id} email={email}"
            )

        usuario.cargo = CargoUsuario.ADMIN
        usuario.ativo = True
        db.commit()
        return True
