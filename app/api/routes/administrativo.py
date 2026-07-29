from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
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

    agendamentos_hoje = db.scalar(
        select(func.count()).select_from(Agendamento).where(
            Agendamento.empresa_id == empresa_id,
            Agendamento.data == today,
            Agendamento.status != StatusAgendamento.CANCELADO,
        )
    ) or 0

    agendamentos_pendentes = db.scalar(
        select(func.count()).select_from(Agendamento).where(
            Agendamento.empresa_id == empresa_id,
            Agendamento.status == StatusAgendamento.PENDENTE,
        )
    ) or 0

    conversas_abertas = db.scalar(
        select(func.count()).select_from(Conversa).where(
            Conversa.empresa_id == empresa_id,
            Conversa.status != StatusConversa.FINALIZADA,
        )
    ) or 0

    clientes_ativos = db.scalar(
        select(func.count()).select_from(Cliente).where(
            Cliente.empresa_id == empresa_id,
            Cliente.status == StatusCliente.ATIVO,
        )
    ) or 0

    notificacoes_nao_lidas = db.scalar(
        select(func.count()).select_from(Notificacao).where(
            Notificacao.empresa_id == empresa_id,
            Notificacao.lida.is_(False),
        )
    ) or 0

    return DashboardOut(
        agendamentos_hoje=agendamentos_hoje,
        agendamentos_pendentes=agendamentos_pendentes,
        conversas_abertas=conversas_abertas,
        clientes_ativos=clientes_ativos,
        notificacoes_nao_lidas=notificacoes_nao_lidas,
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
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
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
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
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
