from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.database.database import get_db
from app.models.enums import (
    CargoUsuario,
    StatusAgendamento,
    StatusCliente,
    StatusConversa,
)
from app.models.models import (
    Agendamento,
    Assinatura,
    Cliente,
    Conversa,
    Log,
    Notificacao,
    Plano,
    Usuario,
)
from app.schemas.entities import (
    AssinaturaOut,
    DashboardOut,
    LogOut,
    PlanoOut,
)

router = APIRouter(prefix="/administrativo", tags=["Administrativo"])


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardOut:
    empresa_id = current_user.empresa_id
    today = date.today()

    agendamentos_hoje = (
        select(func.count())
        .select_from(Agendamento)
        .where(
            Agendamento.empresa_id == empresa_id,
            Agendamento.data == today,
            Agendamento.status != StatusAgendamento.CANCELADO,
        )
        .scalar_subquery()
    )
    agendamentos_pendentes = (
        select(func.count())
        .select_from(Agendamento)
        .where(
            Agendamento.empresa_id == empresa_id,
            Agendamento.status == StatusAgendamento.PENDENTE,
        )
        .scalar_subquery()
    )
    conversas_abertas = (
        select(func.count())
        .select_from(Conversa)
        .where(
            Conversa.empresa_id == empresa_id,
            Conversa.status != StatusConversa.FINALIZADA,
        )
        .scalar_subquery()
    )
    clientes_ativos = (
        select(func.count())
        .select_from(Cliente)
        .where(
            Cliente.empresa_id == empresa_id,
            Cliente.status == StatusCliente.ATIVO,
        )
        .scalar_subquery()
    )
    notificacoes_nao_lidas = (
        select(func.count())
        .select_from(Notificacao)
        .where(
            Notificacao.empresa_id == empresa_id,
            Notificacao.lida.is_(False),
            or_(
                Notificacao.usuario_id.is_(None),
                Notificacao.usuario_id == current_user.id,
            ),
        )
        .scalar_subquery()
    )

    row = db.execute(
        select(
            agendamentos_hoje.label("agendamentos_hoje"),
            agendamentos_pendentes.label("agendamentos_pendentes"),
            conversas_abertas.label("conversas_abertas"),
            clientes_ativos.label("clientes_ativos"),
            notificacoes_nao_lidas.label("notificacoes_nao_lidas"),
        )
    ).one()

    return DashboardOut(
        agendamentos_hoje=int(row.agendamentos_hoje or 0),
        agendamentos_pendentes=int(row.agendamentos_pendentes or 0),
        conversas_abertas=int(row.conversas_abertas or 0),
        clientes_ativos=int(row.clientes_ativos or 0),
        notificacoes_nao_lidas=int(row.notificacoes_nao_lidas or 0),
    )


@router.get("/planos", response_model=list[PlanoOut])
def listar_planos(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Plano]:
    return list(
        db.scalars(select(Plano).where(Plano.ativo.is_(True)).order_by(Plano.preco))
    )


@router.get("/assinaturas", response_model=list[AssinaturaOut])
def listar_assinaturas(
    current_user: Usuario = Depends(require_roles(CargoUsuario.ADMIN)),
    db: Session = Depends(get_db),
) -> list[Assinatura]:
    return list(
        db.scalars(
            select(Assinatura)
            .where(Assinatura.empresa_id == current_user.empresa_id)
            .order_by(Assinatura.created_at.desc())
        )
    )


@router.get("/logs", response_model=list[LogOut])
def listar_logs(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=300),
    current_user: Usuario = Depends(require_roles(CargoUsuario.ADMIN)),
    db: Session = Depends(get_db),
) -> list[Log]:
    return list(
        db.scalars(
            select(Log)
            .where(Log.empresa_id == current_user.empresa_id)
            .order_by(Log.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )
