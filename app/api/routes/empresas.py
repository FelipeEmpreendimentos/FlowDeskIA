from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.config import PROJECT_ROOT
from app.database.database import get_db
from app.models.enums import CargoUsuario
from app.models.models import Empresa, Usuario
from app.schemas.entities import EmpresaOut, EmpresaUpdate
from app.services.audit import add_audit_log
from app.services.db_utils import apply_patch, commit_or_conflict

router = APIRouter(prefix="/empresa", tags=["Empresa"])


COMPANY_LOGOS_DIR = PROJECT_ROOT / "uploads" / "company_logos"
COMPANY_LOGOS_DIR.mkdir(parents=True, exist_ok=True)
MAX_LOGO_SIZE = 2 * 1024 * 1024


def _image_extension(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp"
    return None


def _remove_local_logo(logo_url: str | None) -> None:
    prefix = "/uploads/company_logos/"
    if not logo_url or not logo_url.startswith(prefix):
        return

    filename = Path(logo_url).name
    target = (COMPANY_LOGOS_DIR / filename).resolve()
    if target.parent != COMPANY_LOGOS_DIR.resolve():
        return

    try:
        target.unlink(missing_ok=True)
    except OSError:
        # A falha na limpeza do arquivo antigo não deve impedir o uso do sistema.
        pass


@router.get("", response_model=EmpresaOut)
def obter_empresa(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Empresa:
    empresa = db.get(Empresa, current_user.empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa não encontrada.")
    return empresa


@router.patch("", response_model=EmpresaOut)
def atualizar_empresa(
    data: EmpresaUpdate,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> Empresa:
    empresa = db.get(Empresa, current_user.empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa não encontrada.")

    apply_patch(empresa, data.model_dump(exclude_unset=True))
    add_audit_log(
        db,
        user=current_user,
        action="ATUALIZOU_EMPRESA",
        entity="empresas",
        entity_id=empresa.id,
    )
    return commit_or_conflict(db, empresa)


@router.post("/logo", response_model=EmpresaOut)
async def atualizar_logo_empresa(
    logo: UploadFile = File(...),
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> Empresa:
    empresa = db.get(Empresa, current_user.empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa não encontrada.")

    content = await logo.read(MAX_LOGO_SIZE + 1)
    await logo.close()

    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A imagem está vazia.")
    if len(content) > MAX_LOGO_SIZE:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "A imagem deve ter no máximo 2 MB.",
        )

    extension = _image_extension(content)
    if extension is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Envie uma imagem válida em PNG, JPG ou WebP.",
        )

    filename = f"empresa_{empresa.id}_{uuid4().hex}{extension}"
    target = COMPANY_LOGOS_DIR / filename
    target.write_bytes(content)

    old_logo = empresa.logo
    empresa.logo = f"/uploads/company_logos/{filename}"
    add_audit_log(
        db,
        user=current_user,
        action="ATUALIZOU_LOGO_EMPRESA",
        entity="empresas",
        entity_id=empresa.id,
    )

    try:
        updated = commit_or_conflict(db, empresa)
    except Exception:
        target.unlink(missing_ok=True)
        raise

    _remove_local_logo(old_logo)
    return updated


@router.delete("/logo", response_model=EmpresaOut)
def remover_logo_empresa(
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> Empresa:
    empresa = db.get(Empresa, current_user.empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa não encontrada.")

    old_logo = empresa.logo
    empresa.logo = None
    add_audit_log(
        db,
        user=current_user,
        action="REMOVEU_LOGO_EMPRESA",
        entity="empresas",
        entity_id=empresa.id,
    )
    updated = commit_or_conflict(db, empresa)
    _remove_local_logo(old_logo)
    return updated
