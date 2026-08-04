from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, aliased

from app.api.deps import require_roles
from app.database.database import get_db
from app.models.enums import CargoUsuario, StatusAgendamento
from app.models.finance import FechamentoFinanceiro
from app.models.models import Agendamento, Cliente, Conversa, Servico, Usuario
from app.schemas.reports import (
    AvaliacaoComentarioItem,
    RelatorioAvaliacoesOut,
    RelatorioEvolucaoItem,
    RelatorioFuncionarioItem,
    RelatorioResumoOut,
    RelatorioServicoItem,
)
from app.services.finance import dinheiro
from app.services.plans import require_feature


router = APIRouter(prefix="/relatorios", tags=["Relatórios"])


def _periodo(
    data_inicio: date | None,
    data_fim: date | None,
) -> tuple[date, date]:
    hoje = datetime.now(timezone.utc).date()
    inicio = data_inicio or hoje.replace(day=1)
    fim = data_fim or hoje
    if inicio > fim:
        inicio, fim = fim, inicio
    return inicio, fim


def _datetime_bounds(inicio: date, fim: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(inicio, time.min, tzinfo=timezone.utc),
        datetime.combine(fim, time.max, tzinfo=timezone.utc),
    )


@router.get("/resumo", response_model=RelatorioResumoOut)
def resumo(
    data_inicio: date | None = None,
    data_fim: date | None = None,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> RelatorioResumoOut:
    inicio, fim = _periodo(data_inicio, data_fim)
    inicio_dt, fim_dt = _datetime_bounds(inicio, fim)

    financeiro = db.execute(
        select(
            func.count(FechamentoFinanceiro.id),
            func.coalesce(func.sum(FechamentoFinanceiro.valor_final), 0),
            func.coalesce(func.sum(FechamentoFinanceiro.valor_recebido), 0),
            func.coalesce(func.sum(FechamentoFinanceiro.valor_pendente), 0),
            func.coalesce(func.sum(FechamentoFinanceiro.desconto_valor), 0),
            func.coalesce(func.avg(FechamentoFinanceiro.valor_final), 0),
        )
        .join(Agendamento, Agendamento.id == FechamentoFinanceiro.agendamento_id)
        .where(
            FechamentoFinanceiro.empresa_id == current_user.empresa_id,
            FechamentoFinanceiro.status != "ESTORNADO",
            Agendamento.data >= inicio,
            Agendamento.data <= fim,
        )
    ).one()

    cancelamentos = db.scalar(
        select(func.count(Agendamento.id)).where(
            Agendamento.empresa_id == current_user.empresa_id,
            Agendamento.status == StatusAgendamento.CANCELADO,
            Agendamento.data >= inicio,
            Agendamento.data <= fim,
        )
    ) or 0

    clientes_novos = db.scalar(
        select(func.count(Cliente.id)).where(
            Cliente.empresa_id == current_user.empresa_id,
            Cliente.created_at >= inicio_dt,
            Cliente.created_at <= fim_dt,
        )
    ) or 0

    recorrentes_subquery = (
        select(Agendamento.cliente_id)
        .join(
            FechamentoFinanceiro,
            FechamentoFinanceiro.agendamento_id == Agendamento.id,
        )
        .where(
            Agendamento.empresa_id == current_user.empresa_id,
            Agendamento.data >= inicio,
            Agendamento.data <= fim,
            FechamentoFinanceiro.status != "ESTORNADO",
        )
        .group_by(Agendamento.cliente_id)
        .having(func.count(FechamentoFinanceiro.id) >= 2)
        .subquery()
    )
    clientes_recorrentes = db.scalar(
        select(func.count()).select_from(recorrentes_subquery)
    ) or 0

    return RelatorioResumoOut(
        data_inicio=inicio,
        data_fim=fim,
        atendimentos=int(financeiro[0] or 0),
        faturamento=dinheiro(financeiro[1]),
        recebido=dinheiro(financeiro[2]),
        pendente=dinheiro(financeiro[3]),
        descontos=dinheiro(financeiro[4]),
        ticket_medio=dinheiro(financeiro[5]),
        cancelamentos=int(cancelamentos),
        clientes_novos=int(clientes_novos),
        clientes_recorrentes=int(clientes_recorrentes),
    )


@router.get("/evolucao", response_model=list[RelatorioEvolucaoItem])
def relatorio_evolucao(
    data_inicio: date | None = None,
    data_fim: date | None = None,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> list[RelatorioEvolucaoItem]:
    inicio, fim = _periodo(data_inicio, data_fim)
    rows = db.execute(
        select(
            Agendamento.data,
            func.count(FechamentoFinanceiro.id),
            func.coalesce(func.sum(FechamentoFinanceiro.valor_final), 0),
            func.coalesce(func.sum(FechamentoFinanceiro.valor_recebido), 0),
            func.coalesce(func.sum(FechamentoFinanceiro.valor_pendente), 0),
        )
        .join(
            FechamentoFinanceiro,
            FechamentoFinanceiro.agendamento_id == Agendamento.id,
        )
        .where(
            Agendamento.empresa_id == current_user.empresa_id,
            Agendamento.data >= inicio,
            Agendamento.data <= fim,
            FechamentoFinanceiro.status != "ESTORNADO",
        )
        .group_by(Agendamento.data)
        .order_by(Agendamento.data)
    ).all()

    por_data = {
        row[0]: RelatorioEvolucaoItem(
            data=row[0],
            atendimentos=int(row[1] or 0),
            faturamento=dinheiro(row[2]),
            recebido=dinheiro(row[3]),
            pendente=dinheiro(row[4]),
        )
        for row in rows
    }

    resultado: list[RelatorioEvolucaoItem] = []
    cursor = inicio
    while cursor <= fim:
        resultado.append(
            por_data.get(
                cursor,
                RelatorioEvolucaoItem(
                    data=cursor,
                    atendimentos=0,
                    faturamento=dinheiro(0),
                    recebido=dinheiro(0),
                    pendente=dinheiro(0),
                ),
            )
        )
        cursor += timedelta(days=1)
    return resultado


@router.get("/servicos", response_model=list[RelatorioServicoItem])
def relatorio_servicos(
    data_inicio: date | None = None,
    data_fim: date | None = None,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> list[RelatorioServicoItem]:
    inicio, fim = _periodo(data_inicio, data_fim)

    rows = db.execute(
        select(
            Servico.id,
            Servico.nome,
            func.count(FechamentoFinanceiro.id),
            func.coalesce(func.sum(FechamentoFinanceiro.valor_final), 0),
            func.coalesce(func.sum(FechamentoFinanceiro.valor_recebido), 0),
            func.coalesce(func.avg(FechamentoFinanceiro.valor_final), 0),
        )
        .join(Agendamento, Agendamento.servico_id == Servico.id)
        .join(
            FechamentoFinanceiro,
            FechamentoFinanceiro.agendamento_id == Agendamento.id,
        )
        .where(
            Servico.empresa_id == current_user.empresa_id,
            Agendamento.data >= inicio,
            Agendamento.data <= fim,
            FechamentoFinanceiro.status != "ESTORNADO",
        )
        .group_by(Servico.id, Servico.nome)
        .order_by(func.sum(FechamentoFinanceiro.valor_final).desc())
    ).all()

    return [
        RelatorioServicoItem(
            servico_id=int(row[0]),
            servico_nome=row[1],
            atendimentos=int(row[2] or 0),
            faturamento=dinheiro(row[3]),
            recebido=dinheiro(row[4]),
            ticket_medio=dinheiro(row[5]),
        )
        for row in rows
    ]


@router.get("/funcionarios", response_model=list[RelatorioFuncionarioItem])
def relatorio_funcionarios(
    data_inicio: date | None = None,
    data_fim: date | None = None,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> list[RelatorioFuncionarioItem]:
    inicio, fim = _periodo(data_inicio, data_fim)

    rows = db.execute(
        select(
            Agendamento.funcionario_id,
            func.coalesce(Usuario.nome, "Sem responsável"),
            func.count(FechamentoFinanceiro.id),
            func.coalesce(func.sum(FechamentoFinanceiro.valor_final), 0),
            func.coalesce(func.sum(FechamentoFinanceiro.valor_recebido), 0),
            func.coalesce(func.avg(FechamentoFinanceiro.valor_final), 0),
        )
        .join(
            FechamentoFinanceiro,
            FechamentoFinanceiro.agendamento_id == Agendamento.id,
        )
        .outerjoin(Usuario, Usuario.id == Agendamento.funcionario_id)
        .where(
            Agendamento.empresa_id == current_user.empresa_id,
            Agendamento.data >= inicio,
            Agendamento.data <= fim,
            FechamentoFinanceiro.status != "ESTORNADO",
        )
        .group_by(Agendamento.funcionario_id, Usuario.nome)
        .order_by(func.sum(FechamentoFinanceiro.valor_final).desc())
    ).all()

    return [
        RelatorioFuncionarioItem(
            funcionario_id=int(row[0]) if row[0] is not None else None,
            funcionario_nome=row[1],
            atendimentos=int(row[2] or 0),
            faturamento=dinheiro(row[3]),
            recebido=dinheiro(row[4]),
            ticket_medio=dinheiro(row[5]),
        )
        for row in rows
    ]


@router.get("/avaliacoes", response_model=RelatorioAvaliacoesOut)
def relatorio_avaliacoes(
    data_inicio: date | None = None,
    data_fim: date | None = None,
    limit_comentarios: int = 100,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> RelatorioAvaliacoesOut:
    require_feature(db, current_user.empresa_id, "AVALIACOES")
    inicio, fim = _periodo(data_inicio, data_fim)
    inicio_dt, fim_dt = _datetime_bounds(inicio, fim)

    agregado = db.execute(
        select(
            func.count(Conversa.id),
            func.coalesce(func.avg(Conversa.avaliacao_nota), 0),
            func.coalesce(
                func.sum(case((Conversa.avaliacao_nota <= 2, 1), else_=0)),
                0,
            ),
        ).where(
            Conversa.empresa_id == current_user.empresa_id,
            Conversa.avaliacao_nota.is_not(None),
            Conversa.avaliacao_respondida_em >= inicio_dt,
            Conversa.avaliacao_respondida_em <= fim_dt,
        )
    ).one()

    distribuicao_rows = db.execute(
        select(Conversa.avaliacao_nota, func.count(Conversa.id))
        .where(
            Conversa.empresa_id == current_user.empresa_id,
            Conversa.avaliacao_nota.is_not(None),
            Conversa.avaliacao_respondida_em >= inicio_dt,
            Conversa.avaliacao_respondida_em <= fim_dt,
        )
        .group_by(Conversa.avaliacao_nota)
    ).all()
    notas = {nota: 0 for nota in range(1, 6)}
    for nota, quantidade in distribuicao_rows:
        if nota is not None:
            notas[int(nota)] = int(quantidade)

    responsavel = aliased(Usuario)
    comentarios_rows = db.execute(
        select(Conversa, Cliente, responsavel)
        .join(Cliente, Cliente.id == Conversa.cliente_id)
        .outerjoin(responsavel, responsavel.id == Conversa.responsavel_id)
        .where(
            Conversa.empresa_id == current_user.empresa_id,
            Conversa.avaliacao_nota.is_not(None),
            Conversa.avaliacao_respondida_em >= inicio_dt,
            Conversa.avaliacao_respondida_em <= fim_dt,
        )
        .order_by(Conversa.avaliacao_respondida_em.desc())
        .limit(max(1, min(limit_comentarios, 300)))
    ).all()

    comentarios = [
        AvaliacaoComentarioItem(
            conversa_id=conversa.id,
            cliente_id=cliente.id,
            cliente_nome=cliente.nome,
            funcionario_id=conversa.responsavel_id,
            funcionario_nome=usuario.nome if usuario else None,
            nota=int(conversa.avaliacao_nota),
            comentario=conversa.avaliacao_comentario,
            respondida_em=conversa.avaliacao_respondida_em,
        )
        for conversa, cliente, usuario in comentarios_rows
    ]

    return RelatorioAvaliacoesOut(
        quantidade=int(agregado[0] or 0),
        media=dinheiro(agregado[1]),
        notas=notas,
        avaliacoes_baixas=int(agregado[2] or 0),
        comentarios=comentarios,
    )
