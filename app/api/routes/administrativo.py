from datetime import date, datetime, time

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select, text
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
    NotificacaoOut,
    PlanoOut,
)

router = APIRouter(prefix="/administrativo", tags=["Administrativo"])


class DashboardReferenciaOut(BaseModel):
    id: int
    nome: str


class DashboardAgendamentoOut(BaseModel):
    id: int
    cliente_id: int
    servico_id: int
    hora_inicio: time
    status: StatusAgendamento


class DashboardBootstrapOut(BaseModel):
    resumo: DashboardOut
    agendamentos: list[DashboardAgendamentoOut]
    clientes: list[DashboardReferenciaOut]
    servicos: list[DashboardReferenciaOut]
    notificacoes: list[NotificacaoOut]


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


@router.get("/dashboard/bootstrap", response_model=DashboardBootstrapOut)
def dashboard_bootstrap(
    data: date | None = Query(default=None),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardBootstrapOut:
    """Entrega a visão geral inteira em um único round trip de dados.

    O endpoint antigo continua disponível para compatibilidade. Este bootstrap é
    otimizado para a UI e evita cinco requests HTTP e várias validações repetidas.
    """
    target_date = data or date.today()
    row = db.execute(
        text(
            """
            SELECT
                (
                    SELECT COUNT(*)
                    FROM agendamentos a
                    WHERE a.empresa_id = :empresa_id
                      AND a.data = :target_date
                      AND a.status <> 'CANCELADO'
                ) AS agendamentos_hoje,
                (
                    SELECT COUNT(*)
                    FROM agendamentos a
                    WHERE a.empresa_id = :empresa_id
                      AND a.status = 'PENDENTE'
                ) AS agendamentos_pendentes,
                (
                    SELECT COUNT(*)
                    FROM conversas c
                    WHERE c.empresa_id = :empresa_id
                      AND c.status <> 'FINALIZADA'
                ) AS conversas_abertas,
                (
                    SELECT COUNT(*)
                    FROM clientes c
                    WHERE c.empresa_id = :empresa_id
                      AND c.status = 'ATIVO'
                ) AS clientes_ativos,
                (
                    SELECT COUNT(*)
                    FROM notificacoes n
                    WHERE n.empresa_id = :empresa_id
                      AND n.lida = FALSE
                      AND (n.usuario_id IS NULL OR n.usuario_id = :usuario_id)
                ) AS notificacoes_nao_lidas,
                COALESCE((
                    SELECT jsonb_agg(
                        jsonb_build_object(
                            'id', x.id,
                            'cliente_id', x.cliente_id,
                            'servico_id', x.servico_id,
                            'hora_inicio', x.hora_inicio,
                            'status', x.status
                        )
                        ORDER BY x.hora_inicio
                    )
                    FROM (
                        SELECT id, cliente_id, servico_id, hora_inicio, status::text AS status
                        FROM agendamentos
                        WHERE empresa_id = :empresa_id
                          AND data = :target_date
                          AND status IN ('PENDENTE', 'CONFIRMADO', 'EM_ANDAMENTO')
                        ORDER BY hora_inicio
                        LIMIT 8
                    ) x
                ), '[]'::jsonb) AS agendamentos,
                COALESCE((
                    SELECT jsonb_agg(
                        jsonb_build_object('id', x.id, 'nome', x.nome)
                        ORDER BY x.nome
                    )
                    FROM (
                        SELECT id, nome
                        FROM clientes
                        WHERE empresa_id = :empresa_id
                        ORDER BY nome
                        LIMIT 100
                    ) x
                ), '[]'::jsonb) AS clientes,
                COALESCE((
                    SELECT jsonb_agg(
                        jsonb_build_object('id', x.id, 'nome', x.nome)
                        ORDER BY x.nome
                    )
                    FROM (
                        SELECT id, nome
                        FROM servicos
                        WHERE empresa_id = :empresa_id
                          AND ativo = TRUE
                        ORDER BY nome
                        LIMIT 100
                    ) x
                ), '[]'::jsonb) AS servicos,
                COALESCE((
                    SELECT jsonb_agg(
                        jsonb_build_object(
                            'id', x.id,
                            'empresa_id', x.empresa_id,
                            'usuario_id', x.usuario_id,
                            'titulo', x.titulo,
                            'mensagem', x.mensagem,
                            'lida', x.lida,
                            'created_at', x.created_at
                        )
                        ORDER BY x.created_at DESC
                    )
                    FROM (
                        SELECT id, empresa_id, usuario_id, titulo, mensagem, lida, created_at
                        FROM notificacoes
                        WHERE empresa_id = :empresa_id
                          AND lida = FALSE
                          AND (usuario_id IS NULL OR usuario_id = :usuario_id)
                        ORDER BY created_at DESC
                        LIMIT 4
                    ) x
                ), '[]'::jsonb) AS notificacoes
            """
        ),
        {
            "empresa_id": current_user.empresa_id,
            "usuario_id": current_user.id,
            "target_date": target_date,
        },
    ).mappings().one()

    return DashboardBootstrapOut(
        resumo=DashboardOut(
            agendamentos_hoje=int(row["agendamentos_hoje"] or 0),
            agendamentos_pendentes=int(row["agendamentos_pendentes"] or 0),
            conversas_abertas=int(row["conversas_abertas"] or 0),
            clientes_ativos=int(row["clientes_ativos"] or 0),
            notificacoes_nao_lidas=int(row["notificacoes_nao_lidas"] or 0),
        ),
        agendamentos=[DashboardAgendamentoOut.model_validate(item) for item in row["agendamentos"]],
        clientes=[DashboardReferenciaOut.model_validate(item) for item in row["clientes"]],
        servicos=[DashboardReferenciaOut.model_validate(item) for item in row["servicos"]],
        notificacoes=[NotificacaoOut.model_validate(item) for item in row["notificacoes"]],
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
