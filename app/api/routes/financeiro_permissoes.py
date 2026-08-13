from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.financeiro import (
    STATUS_VALIDOS,
    _get_agendamento,
    _get_fechamento_por_agendamento,
    _pode_operar_agendamento,
    listar_fechamentos as listar_fechamentos_base,
)
from app.core.permissions import is_management
from app.database.database import get_db
from app.models.finance import FechamentoFinanceiro
from app.models.models import Agendamento, Usuario
from app.schemas.finance import FechamentoListaItem, FechamentoOut, ResumoFinanceiroOut
from app.services.finance import dinheiro


router = APIRouter(prefix="/financeiro", tags=["Financeiro"])


@router.get("/fechamentos", response_model=list[FechamentoListaItem])
def listar_fechamentos_com_escopo(
    data_inicio: date | None = None,
    data_fim: date | None = None,
    status_fechamento: str | None = None,
    funcionario_id: int | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FechamentoListaItem]:
    if status_fechamento and status_fechamento not in STATUS_VALIDOS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Status financeiro inválido.",
        )

    funcionario_efetivo = (
        funcionario_id if is_management(current_user) else current_user.id
    )
    return listar_fechamentos_base(
        data_inicio=data_inicio,
        data_fim=data_fim,
        status_fechamento=status_fechamento,
        funcionario_id=funcionario_efetivo,
        offset=offset,
        limit=limit,
        current_user=current_user,
        db=db,
    )


@router.get("/resumo", response_model=ResumoFinanceiroOut)
def resumo_financeiro_com_escopo(
    data_inicio: date | None = None,
    data_fim: date | None = None,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResumoFinanceiroOut:
    query = (
        select(
            func.count(FechamentoFinanceiro.id),
            func.coalesce(func.sum(FechamentoFinanceiro.valor_original), 0),
            func.coalesce(func.sum(FechamentoFinanceiro.desconto_valor), 0),
            func.coalesce(func.sum(FechamentoFinanceiro.valor_final), 0),
            func.coalesce(func.sum(FechamentoFinanceiro.valor_recebido), 0),
            func.coalesce(func.sum(FechamentoFinanceiro.valor_pendente), 0),
            func.coalesce(
                func.sum(
                    case((FechamentoFinanceiro.status == "PENDENTE", 1), else_=0)
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case((FechamentoFinanceiro.status == "PARCIAL", 1), else_=0)
                ),
                0,
            ),
            func.coalesce(
                func.sum(case((FechamentoFinanceiro.status == "PAGO", 1), else_=0)),
                0,
            ),
            func.coalesce(
                func.sum(
                    case((FechamentoFinanceiro.status == "CORTESIA", 1), else_=0)
                ),
                0,
            ),
        )
        .join(Agendamento, Agendamento.id == FechamentoFinanceiro.agendamento_id)
        .where(FechamentoFinanceiro.empresa_id == current_user.empresa_id)
    )
    if not is_management(current_user):
        query = query.where(Agendamento.funcionario_id == current_user.id)
    if data_inicio:
        query = query.where(Agendamento.data >= data_inicio)
    if data_fim:
        query = query.where(Agendamento.data <= data_fim)

    row = db.execute(query).one()
    return ResumoFinanceiroOut(
        quantidade=int(row[0] or 0),
        valor_original=dinheiro(row[1]),
        descontos=dinheiro(row[2]),
        valor_final=dinheiro(row[3]),
        valor_recebido=dinheiro(row[4]),
        valor_pendente=dinheiro(row[5]),
        pendentes=int(row[6] or 0),
        parciais=int(row[7] or 0),
        pagos=int(row[8] or 0),
        cortesias=int(row[9] or 0),
    )


@router.get(
    "/agendamentos/{agendamento_id}/fechamento",
    response_model=FechamentoOut,
)
def obter_fechamento_com_escopo(
    agendamento_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FechamentoFinanceiro:
    agendamento = _get_agendamento(db, current_user.empresa_id, agendamento_id)
    _pode_operar_agendamento(current_user, agendamento)
    fechamento = _get_fechamento_por_agendamento(
        db,
        current_user.empresa_id,
        agendamento_id,
    )
    if fechamento is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Fechamento ainda não criado.",
        )
    return fechamento
