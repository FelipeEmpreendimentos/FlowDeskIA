from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.security import hash_password
from app.database.database import get_db
from app.models.enums import CargoUsuario
from app.models.internal_chat import MensagemChatInterno
from app.models.models import Agendamento, Conversa, Log, Usuario
from app.schemas.entities import UsuarioCreate, UsuarioOut, UsuarioUpdate
from app.services.audit import add_audit_log
from app.services.db_utils import apply_patch, commit_or_conflict
from app.services.notifications import notify_admins
from app.services.plans import enforce_limit

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


def _garantir_nome_unico(
    db: Session,
    *,
    empresa_id: int,
    nome: str,
    ignorar_id: int | None = None,
) -> str:
    normalizado = nome.strip()
    query = select(Usuario.id).where(
        Usuario.empresa_id == empresa_id,
        func.lower(func.trim(Usuario.nome)) == normalizado.lower(),
    )
    if ignorar_id is not None:
        query = query.where(Usuario.id != ignorar_id)
    if db.scalar(query.limit(1)) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Já existe um usuário cadastrado com esse nome.",
        )
    return normalizado


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


def _validar_exclusao_permanente(
    db: Session,
    current_user: Usuario,
    usuario: Usuario,
) -> None:
    if usuario.id == current_user.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Você não pode excluir o próprio usuário.",
        )

    _validar_permissao_sobre_usuario(current_user, usuario)

    if usuario.cargo == CargoUsuario.ADMIN and usuario.ativo:
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

    enforce_limit(db, current_user.empresa_id, "usuarios")
    nome = _garantir_nome_unico(
        db,
        empresa_id=current_user.empresa_id,
        nome=data.nome,
    )
    usuario = Usuario(
        empresa_id=current_user.empresa_id,
        nome=nome,
        email=data.email,
        senha_hash=hash_password(data.senha),
        telefone=data.telefone,
        foto_perfil=data.foto_perfil,
        cargo=data.cargo,
    )
    db.add(usuario)
    db.flush()

    notify_admins(
        db,
        empresa_id=current_user.empresa_id,
        titulo="Novo usuário cadastrado",
        mensagem=(
            f"{current_user.nome} cadastrou {usuario.nome} como {usuario.cargo.value}."
        ),
        exclude_user_ids=(current_user.id,),
    )
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

    if "nome" in values:
        nome_normalizado = values["nome"].strip()
        if nome_normalizado.lower() != usuario.nome.strip().lower():
            nome_normalizado = _garantir_nome_unico(
                db,
                empresa_id=current_user.empresa_id,
                nome=nome_normalizado,
                ignorar_id=usuario.id,
            )
        values["nome"] = nome_normalizado

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
    if novo_ativo is True and not usuario.ativo:
        enforce_limit(db, current_user.empresa_id, "usuarios")

    status_alterado = "ativo" in values and bool(values["ativo"]) != usuario.ativo
    apply_patch(usuario, values)

    if status_alterado:
        action = "REATIVOU_USUARIO" if usuario.ativo else "DESATIVOU_USUARIO"
        descricao = "reativou" if usuario.ativo else "desativou"
    else:
        action = "ATUALIZOU_USUARIO"
        descricao = "atualizou"

    notify_admins(
        db,
        empresa_id=current_user.empresa_id,
        titulo="Alteração na equipe",
        mensagem=f"{current_user.nome} {descricao} o usuário {usuario.nome}.",
        exclude_user_ids=(current_user.id,),
    )
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
    notify_admins(
        db,
        empresa_id=current_user.empresa_id,
        titulo="Usuário desativado",
        mensagem=f"{current_user.nome} desativou o usuário {usuario.nome}.",
        exclude_user_ids=(current_user.id,),
    )
    add_audit_log(
        db,
        user=current_user,
        action="DESATIVOU_USUARIO",
        entity="usuarios",
        entity_id=usuario.id,
    )
    commit_or_conflict(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{usuario_id}/permanente", status_code=status.HTTP_204_NO_CONTENT)
def excluir_usuario_permanentemente(
    usuario_id: int,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> Response:
    usuario = _get_usuario(db, current_user.empresa_id, usuario_id)
    _validar_exclusao_permanente(db, current_user, usuario)

    possui_agendamento = db.scalar(
        select(Agendamento.id)
        .where(
            Agendamento.empresa_id == current_user.empresa_id,
            Agendamento.funcionario_id == usuario.id,
        )
        .limit(1)
    )
    possui_conversa = db.scalar(
        select(Conversa.id)
        .where(
            Conversa.empresa_id == current_user.empresa_id,
            or_(
                Conversa.responsavel_id == usuario.id,
                Conversa.finalizada_por_id == usuario.id,
            ),
        )
        .limit(1)
    )
    possui_mensagem_interna = db.scalar(
        select(MensagemChatInterno.id)
        .where(
            MensagemChatInterno.empresa_id == current_user.empresa_id,
            MensagemChatInterno.usuario_id == usuario.id,
        )
        .limit(1)
    )
    possui_auditoria = db.scalar(
        select(Log.id)
        .where(
            Log.empresa_id == current_user.empresa_id,
            Log.ator_id == usuario.id,
        )
        .limit(1)
    )

    if any(
        item is not None
        for item in (
            possui_agendamento,
            possui_conversa,
            possui_mensagem_interna,
            possui_auditoria,
        )
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Este usuário possui histórico operacional. Desative-o para preservar agendamentos, conversas e auditoria.",
        )

    nome_usuario = usuario.nome
    notify_admins(
        db,
        empresa_id=current_user.empresa_id,
        titulo="Usuário excluído",
        mensagem=f"{current_user.nome} excluiu permanentemente o usuário {nome_usuario}.",
        exclude_user_ids=(current_user.id, usuario.id),
    )
    add_audit_log(
        db,
        user=current_user,
        action="EXCLUIU_USUARIO",
        entity="usuarios",
        entity_id=usuario.id,
        details={"nome": nome_usuario},
    )
    db.delete(usuario)
    commit_or_conflict(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
