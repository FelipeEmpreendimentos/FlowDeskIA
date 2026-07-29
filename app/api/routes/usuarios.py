from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.security import hash_password
from app.database.database import get_db
from app.models.enums import CargoUsuario
from app.models.models import Usuario
from app.schemas.entities import UsuarioCreate, UsuarioOut, UsuarioUpdate
from app.services.audit import add_audit_log
from app.services.db_utils import apply_patch, commit_or_conflict

router = APIRouter(prefix="/usuarios", tags=["Usuários"])


def _get_usuario(
    db: Session,
    empresa_id: int,
    usuario_id: int,
) -> Usuario:
    usuario = db.scalar(
        select(Usuario).where(
            Usuario.id == usuario_id,
            Usuario.empresa_id == empresa_id,
        )
    )
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado.")
    return usuario


def _validar_permissao_sobre_usuario(
    current_user: Usuario,
    usuario: Usuario,
    novo_cargo: CargoUsuario | None = None,
) -> None:
    if current_user.cargo == CargoUsuario.GERENTE:
        if usuario.cargo != CargoUsuario.FUNCIONARIO:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Gerentes podem gerenciar apenas funcionários.",
            )
        if novo_cargo not in (None, CargoUsuario.FUNCIONARIO):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Gerentes podem atribuir apenas o cargo de funcionário.",
            )


def _validar_troca_cargo_admin(
    db: Session,
    current_user: Usuario,
    usuario: Usuario,
    novo_cargo: CargoUsuario | None,
) -> None:
    if (
        usuario.cargo != CargoUsuario.ADMIN
        or novo_cargo in (None, CargoUsuario.ADMIN)
        or not usuario.ativo
    ):
        return

    administradores_ativos = db.scalar(
        select(func.count())
        .select_from(Usuario)
        .where(
            Usuario.empresa_id == current_user.empresa_id,
            Usuario.cargo == CargoUsuario.ADMIN,
            Usuario.ativo.is_(True),
        )
    )
    if int(administradores_ativos or 0) <= 1:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A empresa precisa manter pelo menos um administrador ativo.",
        )


def _validar_desativacao(
    db: Session,
    current_user: Usuario,
    usuario: Usuario,
) -> None:
    if usuario.id == current_user.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Você não pode desativar o próprio usuário.",
        )

    _validar_permissao_sobre_usuario(current_user, usuario)

    if usuario.cargo == CargoUsuario.ADMIN:
        administradores_ativos = db.scalar(
            select(func.count())
            .select_from(Usuario)
            .where(
                Usuario.empresa_id == current_user.empresa_id,
                Usuario.cargo == CargoUsuario.ADMIN,
                Usuario.ativo.is_(True),
            )
        )
        if int(administradores_ativos or 0) <= 1:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "A empresa precisa manter pelo menos um administrador ativo.",
            )


@router.get("", response_model=list[UsuarioOut])
def listar_usuarios(
    ativo: bool | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Usuario]:
    query = select(Usuario).where(Usuario.empresa_id == current_user.empresa_id)
    if ativo is not None:
        query = query.where(Usuario.ativo == ativo)
    return list(db.scalars(query.order_by(Usuario.nome).offset(offset).limit(limit)))


@router.post("", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def criar_usuario(
    data: UsuarioCreate,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> Usuario:
    if current_user.cargo == CargoUsuario.GERENTE and data.cargo != CargoUsuario.FUNCIONARIO:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Gerentes podem criar apenas funcionários.",
        )

    usuario = Usuario(
        empresa_id=current_user.empresa_id,
        nome=data.nome,
        email=data.email,
        senha_hash=hash_password(data.senha),
        telefone=data.telefone,
        foto_perfil=data.foto_perfil,
        cargo=data.cargo,
    )
    db.add(usuario)
    db.flush()
    add_audit_log(
        db,
        user=current_user,
        action="CRIOU_USUARIO",
        entity="usuarios",
        entity_id=usuario.id,
    )
    return commit_or_conflict(
        db,
        usuario,
        "Já existe um usuário com esse e-mail na empresa.",
    )


@router.get("/{usuario_id}", response_model=UsuarioOut)
def obter_usuario(
    usuario_id: int,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> Usuario:
    return _get_usuario(db, current_user.empresa_id, usuario_id)


@router.patch("/{usuario_id}", response_model=UsuarioOut)
def atualizar_usuario(
    usuario_id: int,
    data: UsuarioUpdate,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> Usuario:
    usuario = _get_usuario(db, current_user.empresa_id, usuario_id)
    values = data.model_dump(exclude_unset=True)

    novo_cargo = values.get("cargo")
    _validar_permissao_sobre_usuario(
        current_user,
        usuario,
        novo_cargo,
    )
    _validar_troca_cargo_admin(
        db,
        current_user,
        usuario,
        novo_cargo,
    )

    novo_ativo = values.get("ativo")
    if novo_ativo is False and usuario.ativo:
        _validar_desativacao(db, current_user, usuario)

    status_alterado = "ativo" in values and bool(values["ativo"]) != usuario.ativo
    apply_patch(usuario, values)

    if status_alterado:
        action = "REATIVOU_USUARIO" if usuario.ativo else "DESATIVOU_USUARIO"
    else:
        action = "ATUALIZOU_USUARIO"

    add_audit_log(
        db,
        user=current_user,
        action=action,
        entity="usuarios",
        entity_id=usuario.id,
    )
    return commit_or_conflict(
        db,
        usuario,
        "Já existe um usuário com esse e-mail na empresa.",
    )


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def desativar_usuario(
    usuario_id: int,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> Response:
    usuario = _get_usuario(db, current_user.empresa_id, usuario_id)
    _validar_desativacao(db, current_user, usuario)

    usuario.ativo = False
    add_audit_log(
        db,
        user=current_user,
        action="DESATIVOU_USUARIO",
        entity="usuarios",
        entity_id=usuario.id,
    )
    commit_or_conflict(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
