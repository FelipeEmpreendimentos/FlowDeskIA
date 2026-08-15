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
    VIEW_ONLY_MODULES,
    effective_permission_sets,
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


def _user_permissions_out(
    db: Session,
    user: Usuario,
) -> UserModulePermissionsOut:
    rows = list(
        db.scalars(
            select(UsuarioPermissaoModulo).where(
                UsuarioPermissaoModulo.empresa_id == user.empresa_id,
                UsuarioPermissaoModulo.usuario_id == user.id,
            )
        )
    )
    permissions, management_permissions = effective_permission_sets(db, user)
    return UserModulePermissionsOut(
        user_id=user.id,
        name=user.nome,
        email=user.email,
        role=user.cargo,
        active=user.ativo,
        permissions=permissions,
        management_permissions=management_permissions,
        overrides={
            item.modulo: item.permitido
            for item in rows
            if item.permitido is not None
        },
        management_overrides={
            item.modulo: item.pode_gerenciar
            for item in rows
            if item.pode_gerenciar is not None
            and item.modulo not in VIEW_ONLY_MODULES
        },
    )


@router.get("/me", response_model=CurrentAccessOut)
def current_access(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CurrentAccessOut:
    modules, management = effective_permission_sets(db, current_user)
    return CurrentAccessOut(modules=modules, management=management)


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
        users=[_user_permissions_out(db, user) for user in users],
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
        db.flush()
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
    fields = data.model_fields_set
    if not fields.intersection({"view_allowed", "manage_allowed"}):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Informe a permissão de visualização ou gerenciamento.",
        )
    if module in VIEW_ONLY_MODULES and "manage_allowed" in fields:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Este módulo possui somente permissão de visualização.",
        )

    user = _company_user(db, current_user.empresa_id, user_id)
    row = db.scalar(
        select(UsuarioPermissaoModulo).where(
            UsuarioPermissaoModulo.empresa_id == current_user.empresa_id,
            UsuarioPermissaoModulo.usuario_id == user.id,
            UsuarioPermissaoModulo.modulo == module,
        )
    )

    previous_view = row.permitido if row is not None else None
    previous_manage = row.pode_gerenciar if row is not None else None

    if row is None:
        row = UsuarioPermissaoModulo(
            empresa_id=current_user.empresa_id,
            usuario_id=user.id,
            modulo=module,
            permitido=data.view_allowed if "view_allowed" in fields else None,
            pode_gerenciar=(
                data.manage_allowed if "manage_allowed" in fields else None
            ),
        )
        db.add(row)
        db.flush()
    else:
        if "view_allowed" in fields:
            row.permitido = data.view_allowed
        if "manage_allowed" in fields:
            row.pode_gerenciar = data.manage_allowed
        row.updated_at = datetime.now(timezone.utc)

    # Gerenciar pressupõe conseguir abrir o módulo. Ao liberar gerenciamento,
    # a visualização é liberada junto para evitar uma combinação impossível.
    if "manage_allowed" in fields and data.manage_allowed is True:
        row.permitido = True

    row_id = row.id
    if row.permitido is None and row.pode_gerenciar is None:
        db.delete(row)

    add_audit_log(
        db,
        user=current_user,
        action="ATUALIZOU_PERMISSAO_MODULO",
        entity="usuario_permissoes_modulo",
        entity_id=row_id,
        details={
            "usuario_id": user.id,
            "modulo": module,
            "visualizacao_anterior": previous_view,
            "visualizacao_nova": row.permitido,
            "gerenciamento_anterior": previous_manage,
            "gerenciamento_novo": row.pode_gerenciar,
        },
    )
    db.commit()
    return _user_permissions_out(db, user)
