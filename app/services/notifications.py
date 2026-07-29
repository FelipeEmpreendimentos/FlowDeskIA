from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import CargoUsuario
from app.models.models import Notificacao, Usuario


def notify_user(
    db: Session,
    *,
    empresa_id: int,
    usuario_id: int,
    titulo: str,
    mensagem: str,
) -> None:
    db.add(
        Notificacao(
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            titulo=titulo,
            mensagem=mensagem,
        )
    )


def notify_roles(
    db: Session,
    *,
    empresa_id: int,
    roles: Iterable[CargoUsuario],
    titulo: str,
    mensagem: str,
    exclude_user_ids: Iterable[int] = (),
) -> None:
    excluded = set(exclude_user_ids)
    user_ids = db.scalars(
        select(Usuario.id).where(
            Usuario.empresa_id == empresa_id,
            Usuario.ativo.is_(True),
            Usuario.cargo.in_(tuple(roles)),
        )
    )

    for user_id in user_ids:
        if user_id not in excluded:
            notify_user(
                db,
                empresa_id=empresa_id,
                usuario_id=user_id,
                titulo=titulo,
                mensagem=mensagem,
            )


def notify_management(
    db: Session,
    *,
    empresa_id: int,
    titulo: str,
    mensagem: str,
    exclude_user_ids: Iterable[int] = (),
) -> None:
    notify_roles(
        db,
        empresa_id=empresa_id,
        roles=(CargoUsuario.ADMIN, CargoUsuario.GERENTE),
        titulo=titulo,
        mensagem=mensagem,
        exclude_user_ids=exclude_user_ids,
    )


def notify_admins(
    db: Session,
    *,
    empresa_id: int,
    titulo: str,
    mensagem: str,
    exclude_user_ids: Iterable[int] = (),
) -> None:
    notify_roles(
        db,
        empresa_id=empresa_id,
        roles=(CargoUsuario.ADMIN,),
        titulo=titulo,
        mensagem=mensagem,
        exclude_user_ids=exclude_user_ids,
    )
