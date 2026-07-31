from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.engagement import PreferenciaNotificacao
from app.models.enums import CargoUsuario
from app.models.models import Notificacao, Usuario


CATEGORIAS = {
    "AGENDAMENTOS": "agendamentos",
    "FINANCEIRO": "financeiro",
    "CONVERSAS": "conversas",
    "AVALIACOES": "avaliacoes",
    "INTEGRACOES": "integracoes",
    "PLANOS_LIMITES": "planos_limites",
    "SISTEMA": "sistema",
}


def infer_notification_category(titulo: str) -> str:
    normalizado = titulo.lower()
    if any(item in normalizado for item in ("pagamento", "financeiro", "cobrança")):
        return "FINANCEIRO"
    if any(item in normalizado for item in ("agendamento", "atendimento", "agenda")):
        return "AGENDAMENTOS"
    if any(item in normalizado for item in ("conversa", "mensagem", "cliente aguardando")):
        return "CONVERSAS"
    if any(item in normalizado for item in ("avaliação", "avaliacao", "nota baixa")):
        return "AVALIACOES"
    if any(item in normalizado for item in ("integração", "integracao", "whatsapp", "instagram")):
        return "INTEGRACOES"
    if any(item in normalizado for item in ("plano", "limite", "assinatura", "teste")):
        return "PLANOS_LIMITES"
    return "SISTEMA"


def _categoria_habilitada(
    db: Session,
    *,
    empresa_id: int,
    usuario_id: int,
    categoria: str,
) -> bool:
    campo = CATEGORIAS.get(categoria, "sistema")
    preferencia = db.scalar(
        select(PreferenciaNotificacao).where(
            PreferenciaNotificacao.empresa_id == empresa_id,
            PreferenciaNotificacao.usuario_id == usuario_id,
        )
    )
    if preferencia is None:
        return True
    return bool(getattr(preferencia, campo, True))


def notify_user(
    db: Session,
    *,
    empresa_id: int,
    usuario_id: int,
    titulo: str,
    mensagem: str,
    categoria: str | None = None,
) -> None:
    categoria_efetiva = categoria or infer_notification_category(titulo)
    if not _categoria_habilitada(
        db,
        empresa_id=empresa_id,
        usuario_id=usuario_id,
        categoria=categoria_efetiva,
    ):
        return

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
    categoria: str | None = None,
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
                categoria=categoria,
            )


def notify_management(
    db: Session,
    *,
    empresa_id: int,
    titulo: str,
    mensagem: str,
    exclude_user_ids: Iterable[int] = (),
    categoria: str | None = None,
) -> None:
    notify_roles(
        db,
        empresa_id=empresa_id,
        roles=(CargoUsuario.ADMIN, CargoUsuario.GERENTE),
        titulo=titulo,
        mensagem=mensagem,
        exclude_user_ids=exclude_user_ids,
        categoria=categoria,
    )


def notify_admins(
    db: Session,
    *,
    empresa_id: int,
    titulo: str,
    mensagem: str,
    exclude_user_ids: Iterable[int] = (),
    categoria: str | None = None,
) -> None:
    notify_roles(
        db,
        empresa_id=empresa_id,
        roles=(CargoUsuario.ADMIN,),
        titulo=titulo,
        mensagem=mensagem,
        exclude_user_ids=exclude_user_ids,
        categoria=categoria,
    )
