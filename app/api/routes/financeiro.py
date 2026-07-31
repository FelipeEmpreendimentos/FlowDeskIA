from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.permissions import is_management
from app.database.database import get_db
from app.models.enums import CargoUsuario, StatusAgendamento
from app.models.finance import FechamentoFinanceiro, PagamentoAtendimento
from app.models.models import Agendamento, Cliente, Servico, Usuario
from app.schemas.finance import (
    FechamentoAtualizar,
    FechamentoListaItem,
    FechamentoOut,
    FechamentoSalvar,
    PagamentoInput,
    ResumoFinanceiroOut,
)
from app.services.audit import add_audit_log
from app.services.finance import calcular_fechamento, dinheiro
from app.services.notifications import notify_management


router = APIRouter(prefix="/financeiro", tags=["Financeiro"])


STATUS_VALIDOS = {"PENDENTE", "PARCIAL", "PAGO", "CORTESIA", "ESTORNADO"}


def _get_agendamento(db: Session, empresa_id: int, agendamento_id: int) -> Agendamento:
    agendamento = db.scalar(
        select(Agendamento).where(
            Agendamento.id == agendamento_id,
            Agendamento.empresa_id == empresa_id,
        )
    )
    if agendamento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agendamento não encontrado.")
    return agendamento


def _get_fechamento(
    db: Session,
    empresa_id: int,
    fechamento_id: int,
) -> FechamentoFinanceiro:
    fechamento = db.scalar(
        select(FechamentoFinanceiro)
        .options(selectinload(FechamentoFinanceiro.pagamentos))
        .where(
            FechamentoFinanceiro.id == fechamento_id,
            FechamentoFinanceiro.empresa_id == empresa_id,
        )
    )
    if fechamento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fechamento não encontrado.")
    return fechamento


def _get_fechamento_por_agendamento(
    db: Session,
    empresa_id: int,
    agendamento_id: int,
) -> FechamentoFinanceiro | None:
    return db.scalar(
        select(FechamentoFinanceiro)
        .options(selectinload(FechamentoFinanceiro.pagamentos))
        .where(
            FechamentoFinanceiro.empresa_id == empresa_id,
            FechamentoFinanceiro.agendamento_id == agendamento_id,
        )
    )


def _pode_operar_agendamento(user: Usuario, agendamento: Agendamento) -> None:
    if is_management(user):
        return
    if agendamento.funcionario_id not in (None, user.id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Você só pode registrar pagamentos de atendimentos atribuídos a você.",
        )


def _pagamentos_confirmados(
    fechamento: FechamentoFinanceiro,
) -> list[PagamentoAtendimento]:
    return [item for item in fechamento.pagamentos if item.status == "CONFIRMADO"]


def _valor_original(agendamento: Agendamento) -> Decimal:
    if agendamento.valor_final is not None:
        return dinheiro(agendamento.valor_final)
    return dinheiro(agendamento.valor_base) + dinheiro(agendamento.valor_adicional)


def _aplicar_calculo(
    fechamento: FechamentoFinanceiro,
    *,
    desconto_tipo: str | None,
    desconto_valor: Decimal,
    cortesia: bool,
    pagamentos: list[Decimal],
) -> None:
    try:
        calculo = calcular_fechamento(
            valor_original=fechamento.valor_original,
            desconto_tipo=desconto_tipo,
            desconto_informado=desconto_valor,
            pagamentos=pagamentos,
            cortesia=cortesia,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    fechamento.desconto_tipo = None if cortesia else desconto_tipo
    fechamento.desconto_valor = calculo.desconto_valor
    fechamento.valor_final = calculo.valor_final
    fechamento.valor_recebido = calculo.valor_recebido
    fechamento.valor_pendente = calculo.valor_pendente
    fechamento.status = calculo.status
    fechamento.updated_at = datetime.now(timezone.utc)


def _atualizar_forma_pagamento_agendamento(
    agendamento: Agendamento,
    pagamentos: list[PagamentoAtendimento],
) -> None:
    confirmados = [item for item in pagamentos if item.status == "CONFIRMADO"]
    if len(confirmados) == 1:
        agendamento.forma_pagamento = confirmados[0].forma_pagamento
    else:
        agendamento.forma_pagamento = None


@router.get("/fechamentos", response_model=list[FechamentoListaItem])
def listar_fechamentos(
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
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Status financeiro inválido.")

    funcionario = Usuario
    query = (
        select(
            FechamentoFinanceiro,
            Agendamento,
            Cliente,
            Servico,
            funcionario,
        )
        .join(
            Agendamento,
            Agendamento.id == FechamentoFinanceiro.agendamento_id,
        )
        .join(Cliente, Cliente.id == Agendamento.cliente_id)
        .join(Servico, Servico.id == Agendamento.servico_id)
        .outerjoin(funcionario, funcionario.id == Agendamento.funcionario_id)
        .where(FechamentoFinanceiro.empresa_id == current_user.empresa_id)
    )

    if data_inicio:
        query = query.where(Agendamento.data >= data_inicio)
    if data_fim:
        query = query.where(Agendamento.data <= data_fim)
    if status_fechamento:
        query = query.where(FechamentoFinanceiro.status == status_fechamento)
    if funcionario_id:
        query = query.where(Agendamento.funcionario_id == funcionario_id)

    rows = db.execute(
        query.order_by(Agendamento.data.desc(), Agendamento.hora_inicio.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    fechamento_ids = [row[0].id for row in rows]
    principais: dict[int, str | None] = {item_id: None for item_id in fechamento_ids}
    if fechamento_ids:
        pagamentos = db.execute(
            select(
                PagamentoAtendimento.fechamento_id,
                PagamentoAtendimento.forma_pagamento,
                func.count(PagamentoAtendimento.id),
            )
            .where(
                PagamentoAtendimento.empresa_id == current_user.empresa_id,
                PagamentoAtendimento.fechamento_id.in_(fechamento_ids),
                PagamentoAtendimento.status == "CONFIRMADO",
            )
            .group_by(
                PagamentoAtendimento.fechamento_id,
                PagamentoAtendimento.forma_pagamento,
            )
        ).all()
        por_fechamento: dict[int, list[str]] = {}
        for fechamento_id, forma_pagamento, _ in pagamentos:
            por_fechamento.setdefault(fechamento_id, []).append(forma_pagamento)
        for fechamento_id, formas in por_fechamento.items():
            principais[fechamento_id] = formas[0] if len(formas) == 1 else None

    resultado: list[FechamentoListaItem] = []
    for fechamento, agendamento, cliente, servico, usuario in rows:
        resultado.append(
            FechamentoListaItem(
                id=fechamento.id,
                agendamento_id=agendamento.id,
                data=agendamento.data,
                hora_inicio=agendamento.hora_inicio.strftime("%H:%M"),
                cliente_id=cliente.id,
                cliente_nome=cliente.nome,
                servico_id=servico.id,
                servico_nome=servico.nome,
                funcionario_id=agendamento.funcionario_id,
                funcionario_nome=usuario.nome if usuario else None,
                valor_original=fechamento.valor_original,
                desconto_valor=fechamento.desconto_valor,
                valor_final=fechamento.valor_final,
                valor_recebido=fechamento.valor_recebido,
                valor_pendente=fechamento.valor_pendente,
                status=fechamento.status,
                forma_pagamento_principal=principais.get(fechamento.id),
                fechado_em=fechamento.fechado_em,
            )
        )
    return resultado


@router.get("/resumo", response_model=ResumoFinanceiroOut)
def resumo_financeiro(
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
                func.sum(case((FechamentoFinanceiro.status == "PENDENTE", 1), else_=0)),
                0,
            ),
            func.coalesce(
                func.sum(case((FechamentoFinanceiro.status == "PARCIAL", 1), else_=0)),
                0,
            ),
            func.coalesce(
                func.sum(case((FechamentoFinanceiro.status == "PAGO", 1), else_=0)),
                0,
            ),
            func.coalesce(
                func.sum(case((FechamentoFinanceiro.status == "CORTESIA", 1), else_=0)),
                0,
            ),
        )
        .join(Agendamento, Agendamento.id == FechamentoFinanceiro.agendamento_id)
        .where(FechamentoFinanceiro.empresa_id == current_user.empresa_id)
    )
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


@router.get("/agendamentos/{agendamento_id}/fechamento", response_model=FechamentoOut)
def obter_fechamento_agendamento(
    agendamento_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FechamentoFinanceiro:
    _get_agendamento(db, current_user.empresa_id, agendamento_id)
    fechamento = _get_fechamento_por_agendamento(
        db,
        current_user.empresa_id,
        agendamento_id,
    )
    if fechamento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fechamento ainda não criado.")
    return fechamento


@router.post("/agendamentos/{agendamento_id}/fechamento", response_model=FechamentoOut)
def salvar_fechamento(
    agendamento_id: int,
    data: FechamentoSalvar,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FechamentoFinanceiro:
    agendamento = _get_agendamento(db, current_user.empresa_id, agendamento_id)
    _pode_operar_agendamento(current_user, agendamento)

    if agendamento.status == StatusAgendamento.CANCELADO:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Não é possível fechar financeiramente um agendamento cancelado.",
        )

    if not is_management(current_user) and (
        data.cortesia
        or data.desconto_tipo is not None
        or dinheiro(data.desconto_valor) > 0
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Somente administradores e gerentes podem conceder descontos ou cortesias.",
        )

    fechamento = _get_fechamento_por_agendamento(
        db,
        current_user.empresa_id,
        agendamento.id,
    )
    if fechamento is None:
        fechamento = FechamentoFinanceiro(
            empresa_id=current_user.empresa_id,
            agendamento_id=agendamento.id,
            valor_original=_valor_original(agendamento),
            valor_final=_valor_original(agendamento),
            valor_pendente=_valor_original(agendamento),
            status="PENDENTE",
            fechado_por_id=current_user.id,
        )
        db.add(fechamento)
        db.flush()
    elif _pagamentos_confirmados(fechamento) and not is_management(current_user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Somente administradores e gerentes podem substituir um fechamento com pagamentos.",
        )

    for pagamento in _pagamentos_confirmados(fechamento):
        pagamento.status = "ESTORNADO"

    novos_pagamentos: list[PagamentoAtendimento] = []
    for pagamento in data.pagamentos:
        item = PagamentoAtendimento(
            empresa_id=current_user.empresa_id,
            fechamento_id=fechamento.id,
            forma_pagamento=pagamento.forma_pagamento.value,
            valor=dinheiro(pagamento.valor),
            recebido_em=pagamento.recebido_em or datetime.now(timezone.utc),
            registrado_por_id=current_user.id,
            observacoes=pagamento.observacoes,
        )
        db.add(item)
        novos_pagamentos.append(item)

    _aplicar_calculo(
        fechamento,
        desconto_tipo=data.desconto_tipo,
        desconto_valor=data.desconto_valor,
        cortesia=data.cortesia,
        pagamentos=[item.valor for item in novos_pagamentos],
    )
    fechamento.observacoes = data.observacoes
    fechamento.fechado_por_id = fechamento.fechado_por_id or current_user.id
    fechamento.atualizado_por_id = current_user.id
    fechamento.fechado_em = datetime.now(timezone.utc)

    agendamento.status = StatusAgendamento.FINALIZADO
    agendamento.finalizado_em = agendamento.finalizado_em or datetime.now(timezone.utc)
    agendamento.valor_final = fechamento.valor_final
    _atualizar_forma_pagamento_agendamento(agendamento, novos_pagamentos)

    cliente = db.get(Cliente, agendamento.cliente_id)
    if cliente and cliente.empresa_id == current_user.empresa_id:
        cliente.ultima_visita = datetime.now(timezone.utc)

    if fechamento.valor_pendente > 0:
        notify_management(
            db,
            empresa_id=current_user.empresa_id,
            titulo="Pagamento pendente",
            mensagem=(
                f"O atendimento #{agendamento.id} foi finalizado com "
                f"R$ {fechamento.valor_pendente:.2f} pendente."
            ),
            exclude_user_ids=(current_user.id,),
        )

    add_audit_log(
        db,
        user=current_user,
        action="FECHOU_ATENDIMENTO",
        entity="fechamentos_financeiros",
        entity_id=fechamento.id,
        details={
            "agendamento_id": agendamento.id,
            "valor_original": str(fechamento.valor_original),
            "desconto": str(fechamento.desconto_valor),
            "valor_final": str(fechamento.valor_final),
            "valor_recebido": str(fechamento.valor_recebido),
            "valor_pendente": str(fechamento.valor_pendente),
            "status": fechamento.status,
        },
    )
    db.commit()
    db.refresh(fechamento)
    return _get_fechamento(db, current_user.empresa_id, fechamento.id)


@router.post("/fechamentos/{fechamento_id}/pagamentos", response_model=FechamentoOut)
def registrar_pagamento(
    fechamento_id: int,
    data: PagamentoInput,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FechamentoFinanceiro:
    fechamento = _get_fechamento(db, current_user.empresa_id, fechamento_id)
    agendamento = _get_agendamento(
        db,
        current_user.empresa_id,
        fechamento.agendamento_id,
    )
    _pode_operar_agendamento(current_user, agendamento)

    if fechamento.status in {"CORTESIA", "ESTORNADO"}:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Este fechamento não aceita novos pagamentos.",
        )

    pagamento = PagamentoAtendimento(
        empresa_id=current_user.empresa_id,
        fechamento_id=fechamento.id,
        forma_pagamento=data.forma_pagamento.value,
        valor=dinheiro(data.valor),
        recebido_em=data.recebido_em or datetime.now(timezone.utc),
        registrado_por_id=current_user.id,
        observacoes=data.observacoes,
    )

    valores = [item.valor for item in _pagamentos_confirmados(fechamento)]
    valores.append(pagamento.valor)
    _aplicar_calculo(
        fechamento,
        desconto_tipo=fechamento.desconto_tipo,
        desconto_valor=fechamento.desconto_valor,
        cortesia=False,
        pagamentos=valores,
    )
    fechamento.atualizado_por_id = current_user.id
    db.add(pagamento)
    db.flush()

    _atualizar_forma_pagamento_agendamento(
        agendamento,
        [*_pagamentos_confirmados(fechamento), pagamento],
    )
    agendamento.valor_final = fechamento.valor_final

    add_audit_log(
        db,
        user=current_user,
        action="REGISTROU_PAGAMENTO",
        entity="pagamentos_atendimento",
        entity_id=pagamento.id,
        details={
            "fechamento_id": fechamento.id,
            "forma_pagamento": pagamento.forma_pagamento,
            "valor": str(pagamento.valor),
            "valor_pendente": str(fechamento.valor_pendente),
        },
    )
    db.commit()
    return _get_fechamento(db, current_user.empresa_id, fechamento.id)


@router.patch("/fechamentos/{fechamento_id}", response_model=FechamentoOut)
def atualizar_fechamento(
    fechamento_id: int,
    data: FechamentoAtualizar,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FechamentoFinanceiro:
    if current_user.cargo not in {CargoUsuario.ADMIN, CargoUsuario.GERENTE}:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Somente administradores e gerentes podem ajustar o fechamento.",
        )

    fechamento = _get_fechamento(db, current_user.empresa_id, fechamento_id)
    pagamentos = _pagamentos_confirmados(fechamento)
    _aplicar_calculo(
        fechamento,
        desconto_tipo=data.desconto_tipo,
        desconto_valor=data.desconto_valor,
        cortesia=data.cortesia,
        pagamentos=[item.valor for item in pagamentos],
    )
    fechamento.observacoes = data.observacoes
    fechamento.atualizado_por_id = current_user.id

    agendamento = _get_agendamento(
        db,
        current_user.empresa_id,
        fechamento.agendamento_id,
    )
    agendamento.valor_final = fechamento.valor_final
    _atualizar_forma_pagamento_agendamento(agendamento, pagamentos)

    add_audit_log(
        db,
        user=current_user,
        action="AJUSTOU_FECHAMENTO",
        entity="fechamentos_financeiros",
        entity_id=fechamento.id,
        details={
            "desconto": str(fechamento.desconto_valor),
            "valor_final": str(fechamento.valor_final),
            "status": fechamento.status,
        },
    )
    db.commit()
    return _get_fechamento(db, current_user.empresa_id, fechamento.id)


@router.post("/pagamentos/{pagamento_id}/estornar", response_model=FechamentoOut)
def estornar_pagamento(
    pagamento_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FechamentoFinanceiro:
    if current_user.cargo not in {CargoUsuario.ADMIN, CargoUsuario.GERENTE}:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Somente administradores e gerentes podem estornar pagamentos.",
        )

    pagamento = db.scalar(
        select(PagamentoAtendimento).where(
            PagamentoAtendimento.id == pagamento_id,
            PagamentoAtendimento.empresa_id == current_user.empresa_id,
        )
    )
    if pagamento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pagamento não encontrado.")
    if pagamento.status == "ESTORNADO":
        raise HTTPException(status.HTTP_409_CONFLICT, "Pagamento já estornado.")

    pagamento.status = "ESTORNADO"
    fechamento = _get_fechamento(
        db,
        current_user.empresa_id,
        pagamento.fechamento_id,
    )
    restantes = [
        item
        for item in _pagamentos_confirmados(fechamento)
        if item.id != pagamento.id
    ]
    _aplicar_calculo(
        fechamento,
        desconto_tipo=fechamento.desconto_tipo,
        desconto_valor=fechamento.desconto_valor,
        cortesia=False,
        pagamentos=[item.valor for item in restantes],
    )
    fechamento.atualizado_por_id = current_user.id

    agendamento = _get_agendamento(
        db,
        current_user.empresa_id,
        fechamento.agendamento_id,
    )
    _atualizar_forma_pagamento_agendamento(agendamento, restantes)

    add_audit_log(
        db,
        user=current_user,
        action="ESTORNOU_PAGAMENTO",
        entity="pagamentos_atendimento",
        entity_id=pagamento.id,
        details={
            "fechamento_id": fechamento.id,
            "valor": str(pagamento.valor),
            "valor_pendente": str(fechamento.valor_pendente),
        },
    )
    db.commit()
    return _get_fechamento(db, current_user.empresa_id, fechamento.id)
