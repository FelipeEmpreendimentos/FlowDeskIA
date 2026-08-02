from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.database.database import get_db
from app.models.access_control import EmpresaModulo, UsuarioPermissaoModulo
from app.models.enums import CargoUsuario
from app.models.models import Usuario
from app.schemas.access_control import (
    AccessConfigurationOut,
    CompanyModuleOut,
    CompanyModuleUpdate,
    CurrentAccessOut,
    UserModulePermissionUpdate,
    UserModulePermissionsOut,
)
from app.services.access_control import (
    MODULES,
    company_module_enabled,
    default_access,
    effective_permissions,
    validate_module,
)
from app.services.audit import add_audit_log


router = APIRouter(prefix="/acessos", tags=["Módulos e permissões"])


def _company_user(db: Session, empresa_id: int, user_id: int) -> Usuario:
    user = db.scalar(
        select(Usuario).where(
            Usuario.id == user_id,
            Usuario.empresa_id == empresa_id,
        )
    )
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado.")
    return user


@router.get("/me", response_model=CurrentAccessOut)
def current_access(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CurrentAccessOut:
    return CurrentAccessOut(modules=effective_permissions(db, current_user))


@router.get("/configuracao", response_model=AccessConfigurationOut)
def access_configuration(
    current_user: Usuario = Depends(require_roles(CargoUsuario.ADMIN)),
    db: Session = Depends(get_db),
) -> AccessConfigurationOut:
    company_rows = {
        row.modulo: row
        for row in db.scalars(
            select(EmpresaModulo).where(
                EmpresaModulo.empresa_id == current_user.empresa_id
            )
        )
    }
    override_rows = list(
        db.scalars(
            select(UsuarioPermissaoModulo).where(
                UsuarioPermissaoModulo.empresa_id == current_user.empresa_id
            )
        )
    )
    overrides_by_user: dict[int, dict[str, bool]] = {}
    for row in override_rows:
        overrides_by_user.setdefault(row.usuario_id, {})[row.modulo] = row.permitido

    users = list(
        db.scalars(
            select(Usuario)
            .where(Usuario.empresa_id == current_user.empresa_id)
            .order_by(Usuario.nome, Usuario.id)
        )
    )

    return AccessConfigurationOut(
        modules=[
            CompanyModuleOut(
                code=definition.code,
                name=definition.name,
                description=definition.description,
                enabled=(
                    company_rows[definition.code].ativo
                    if definition.code in company_rows
                    else True
                ),
            )
            for definition in MODULES
        ],
        users=[
            UserModulePermissionsOut(
                user_id=user.id,
                name=user.nome,
                email=user.email,
                role=user.cargo,
                active=user.ativo,
                permissions=effective_permissions(db, user),
                overrides=overrides_by_user.get(user.id, {}),
            )
            for user in users
        ],
    )


@router.patch("/modulos/{module}", response_model=CompanyModuleOut)
def update_company_module(
    module: str,
    data: CompanyModuleUpdate,
    current_user: Usuario = Depends(require_roles(CargoUsuario.ADMIN)),
    db: Session = Depends(get_db),
) -> CompanyModuleOut:
    module = validate_module(module)
    definition = next(item for item in MODULES if item.code == module)
    row = db.scalar(
        select(EmpresaModulo).where(
            EmpresaModulo.empresa_id == current_user.empresa_id,
            EmpresaModulo.modulo == module,
        )
    )
    before = True if row is None else row.ativo
    if row is None:
        row = EmpresaModulo(
            empresa_id=current_user.empresa_id,
            modulo=module,
            ativo=data.enabled,
        )
        db.add(row)
    else:
        row.ativo = data.enabled
        row.updated_at = datetime.now(timezone.utc)

    add_audit_log(
        db,
        user=current_user,
        action="ATUALIZOU_MODULO_EMPRESA",
        entity="empresa_modulos",
        entity_id=row.id,
        details={"modulo": module, "anterior": before, "novo": data.enabled},
    )
    db.commit()
    db.refresh(row)
    return CompanyModuleOut(
        code=definition.code,
        name=definition.name,
        description=definition.description,
        enabled=row.ativo,
    )


@router.patch(
    "/usuarios/{user_id}/modulos/{module}",
    response_model=UserModulePermissionsOut,
)
def update_user_module_permission(
    user_id: int,
    module: str,
    data: UserModulePermissionUpdate,
    current_user: Usuario = Depends(require_roles(CargoUsuario.ADMIN)),
    db: Session = Depends(get_db),
) -> UserModulePermissionsOut:
    module = validate_module(module)
    user = _company_user(db, current_user.empresa_id, user_id)
    row = db.scalar(
        select(UsuarioPermissaoModulo).where(
            UsuarioPermissaoModulo.empresa_id == current_user.empresa_id,
            UsuarioPermissaoModulo.usuario_id == user.id,
            UsuarioPermissaoModulo.modulo == module,
        )
    )

    previous = row.permitido if row is not None else None
    if data.allowed is None:
        if row is not None:
            db.delete(row)
    elif row is None:
        row = UsuarioPermissaoModulo(
            empresa_id=current_user.empresa_id,
            usuario_id=user.id,
            modulo=module,
            permitido=data.allowed,
        )
        db.add(row)
    else:
        row.permitido = data.allowed
        row.updated_at = datetime.now(timezone.utc)

    add_audit_log(
        db,
        user=current_user,
        action="ATUALIZOU_PERMISSAO_MODULO",
        entity="usuario_permissoes_modulo",
        entity_id=row.id if row is not None else None,
        details={
            "usuario_id": user.id,
            "modulo": module,
            "anterior": previous,
            "novo": data.allowed,
        },
    )
    db.commit()

    current_overrides = {
        item.modulo: item.permitido
        for item in db.scalars(
            select(UsuarioPermissaoModulo).where(
                UsuarioPermissaoModulo.empresa_id == current_user.empresa_id,
                UsuarioPermissaoModulo.usuario_id == user.id,
            )
        )
    }
    return UserModulePermissionsOut(
        user_id=user.id,
        name=user.nome,
        email=user.email,
        role=user.cargo,
        active=user.ativo,
        permissions=effective_permissions(db, user),
        overrides=current_overrides,
    )
