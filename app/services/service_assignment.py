from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time

from fastapi import HTTPException, status
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.models.enums import StatusAgendamento
from app.models.models import Agendamento, Servico, Usuario
from app.services.agenda import available_slots, ensure_available


STATUS_QUE_OCUPAM_AGENDA = {
    StatusAgendamento.PENDENTE,
    StatusAgendamento.CONFIRMADO,
    StatusAgendamento.EM_ANDAMENTO,
}


def _ids_configurados(
    db: Session,
    *,
    empresa_id: int,
    servico_id: int,
) -> list[int]:
    return [
        int(item)
        for item in db.execute(
            text(
                """
                SELECT sf.funcionario_id
                FROM servico_funcionarios sf
                JOIN usuarios u ON u.id = sf.funcionario_id
                WHERE sf.empresa_id = :empresa_id
                  AND sf.servico_id = :servico_id
                  AND u.empresa_id = :empresa_id
                  AND u.ativo = TRUE
                ORDER BY u.nome, u.id
                """
            ),
            {"empresa_id": empresa_id, "servico_id": servico_id},
        ).scalars()
    ]


def qualified_employee_ids(
    db: Session,
    *,
    empresa_id: int,
    servico_id: int,
) -> list[int]:
    """Retorna os profissionais aptos para um serviço.

    Serviços criados depois da migração ainda sem configuração explícita usam
    todos os usuários ativos como padrão. Assim o comportamento atual continua
    funcionando até a empresa personalizar a equipe daquele serviço.
    """
    configurados = _ids_configurados(
        db,
        empresa_id=empresa_id,
        servico_id=servico_id,
    )
    if configurados:
        return configurados

    return [
        int(item)
        for item in db.scalars(
            select(Usuario.id)
            .where(
                Usuario.empresa_id == empresa_id,
                Usuario.ativo.is_(True),
            )
            .order_by(Usuario.nome, Usuario.id)
        )
    ]


def qualification_map(db: Session, *, empresa_id: int) -> dict[int, list[int]]:
    servicos = list(
        db.scalars(
            select(Servico)
            .where(Servico.empresa_id == empresa_id)
            .order_by(Servico.nome, Servico.id)
        )
    )
    return {
        servico.id: qualified_employee_ids(
            db,
            empresa_id=empresa_id,
            servico_id=servico.id,
        )
        for servico in servicos
    }


def save_service_qualification(
    db: Session,
    *,
    empresa_id: int,
    servico_id: int,
    funcionario_ids: list[int],
) -> list[int]:
    ids = sorted(set(funcionario_ids))
    if not ids:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Selecione pelo menos um funcionário para realizar este serviço.",
        )

    validos = set(
        db.scalars(
            select(Usuario.id).where(
                Usuario.empresa_id == empresa_id,
                Usuario.id.in_(ids),
                Usuario.ativo.is_(True),
            )
        )
    )
    if validos != set(ids):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Um ou mais funcionários selecionados não estão ativos nesta empresa.",
        )

    db.execute(
        text(
            "DELETE FROM servico_funcionarios WHERE empresa_id = :empresa_id AND servico_id = :servico_id"
        ),
        {"empresa_id": empresa_id, "servico_id": servico_id},
    )
    for funcionario_id in ids:
        db.execute(
            text(
                """
                INSERT INTO servico_funcionarios (empresa_id, servico_id, funcionario_id)
                VALUES (:empresa_id, :servico_id, :funcionario_id)
                ON CONFLICT (servico_id, funcionario_id) DO NOTHING
                """
            ),
            {
                "empresa_id": empresa_id,
                "servico_id": servico_id,
                "funcionario_id": funcionario_id,
            },
        )
    db.commit()
    return ids


def ensure_employee_qualified(
    db: Session,
    *,
    empresa_id: int,
    servico_id: int,
    funcionario_id: int,
) -> None:
    if funcionario_id not in qualified_employee_ids(
        db,
        empresa_id=empresa_id,
        servico_id=servico_id,
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Este funcionário não realiza o serviço selecionado.",
        )


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _ranking_context(
    db: Session,
    *,
    empresa_id: int,
    target_date: date,
    funcionario_ids: list[int],
) -> tuple[dict[int, list[Agendamento]], dict[int, int], dict[int, float]]:
    if not funcionario_ids:
        return {}, {}, {}

    itens = list(
        db.scalars(
            select(Agendamento)
            .where(
                Agendamento.empresa_id == empresa_id,
                Agendamento.funcionario_id.in_(funcionario_ids),
                Agendamento.data == target_date,
                Agendamento.status.in_(STATUS_QUE_OCUPAM_AGENDA),
            )
            .order_by(Agendamento.funcionario_id, Agendamento.hora_inicio)
        )
    )
    por_funcionario: dict[int, list[Agendamento]] = defaultdict(list)
    for item in itens:
        if item.funcionario_id is not None:
            por_funcionario[item.funcionario_id].append(item)

    carga = {funcionario_id: len(por_funcionario.get(funcionario_id, [])) for funcionario_id in funcionario_ids}

    ultimas = db.execute(
        text(
            """
            SELECT funcionario_id, MAX(created_at) AS ultima_atribuicao
            FROM agendamentos
            WHERE empresa_id = :empresa_id
              AND funcionario_id = ANY(:funcionario_ids)
            GROUP BY funcionario_id
            """
        ),
        {"empresa_id": empresa_id, "funcionario_ids": funcionario_ids},
    ).all()
    ultima_atribuicao: dict[int, float] = {funcionario_id: 0.0 for funcionario_id in funcionario_ids}
    for funcionario_id, valor in ultimas:
        if valor is not None:
            ultima_atribuicao[int(funcionario_id)] = valor.timestamp()

    return por_funcionario, carga, ultima_atribuicao


def _gap_ate_proximo(
    compromissos: list[Agendamento],
    *,
    slot_end: time,
) -> int:
    fim = _minutes(slot_end)
    proximos = [
        _minutes(item.hora_inicio)
        for item in compromissos
        if item.hora_inicio >= slot_end
    ]
    if not proximos:
        return 24 * 60
    return max(0, min(proximos) - fim)


def smart_available_slots(
    db: Session,
    *,
    empresa_id: int,
    target_date: date,
    service: Servico,
    interval_minutes: int,
) -> list[tuple[time, time, int]]:
    """Distribui cada horário ao melhor profissional apto.

    Critérios, nesta ordem:
    1. menor quantidade de agendamentos no dia;
    2. maior intervalo livre até o próximo atendimento;
    3. quem recebeu uma atribuição há mais tempo;
    4. id apenas como desempate estável final.
    """
    funcionario_ids = qualified_employee_ids(
        db,
        empresa_id=empresa_id,
        servico_id=service.id,
    )
    por_funcionario, carga, ultima_atribuicao = _ranking_context(
        db,
        empresa_id=empresa_id,
        target_date=target_date,
        funcionario_ids=funcionario_ids,
    )

    escolhidos: dict[tuple[time, time], tuple[tuple[float, ...], int]] = {}
    for funcionario_id in funcionario_ids:
        slots = available_slots(
            db,
            empresa_id=empresa_id,
            target_date=target_date,
            funcionario_id=funcionario_id,
            service=service,
            interval_minutes=interval_minutes,
        )
        for start, end in slots:
            gap = _gap_ate_proximo(
                por_funcionario.get(funcionario_id, []),
                slot_end=end,
            )
            ranking = (
                float(carga.get(funcionario_id, 0)),
                float(-gap),
                float(ultima_atribuicao.get(funcionario_id, 0.0)),
                float(funcionario_id),
            )
            chave = (start, end)
            atual = escolhidos.get(chave)
            if atual is None or ranking < atual[0]:
                escolhidos[chave] = (ranking, funcionario_id)

    return [
        (start, end, escolhidos[(start, end)][1])
        for start, end in sorted(escolhidos, key=lambda item: item[0])
    ]


def smart_employee_for_slot(
    db: Session,
    *,
    empresa_id: int,
    target_date: date,
    service: Servico,
    start: time,
    end: time,
) -> int:
    funcionario_ids = qualified_employee_ids(
        db,
        empresa_id=empresa_id,
        servico_id=service.id,
    )
    por_funcionario, carga, ultima_atribuicao = _ranking_context(
        db,
        empresa_id=empresa_id,
        target_date=target_date,
        funcionario_ids=funcionario_ids,
    )
    candidatos: list[tuple[tuple[float, ...], int]] = []

    for funcionario_id in funcionario_ids:
        try:
            ensure_available(
                db,
                empresa_id=empresa_id,
                target_date=target_date,
                start=start,
                end=end,
                funcionario_id=funcionario_id,
            )
        except HTTPException as exc:
            if exc.status_code == status.HTTP_409_CONFLICT:
                continue
            raise

        # Além de conflito/bloqueio, exige que o horário pertença à jornada real.
        if not any(
            slot_start == start and slot_end == end
            for slot_start, slot_end in available_slots(
                db,
                empresa_id=empresa_id,
                target_date=target_date,
                funcionario_id=funcionario_id,
                service=service,
                interval_minutes=1,
            )
        ):
            continue

        gap = _gap_ate_proximo(
            por_funcionario.get(funcionario_id, []),
            slot_end=end,
        )
        ranking = (
            float(carga.get(funcionario_id, 0)),
            float(-gap),
            float(ultima_atribuicao.get(funcionario_id, 0.0)),
            float(funcionario_id),
        )
        candidatos.append((ranking, funcionario_id))

    if not candidatos:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Nenhum funcionário habilitado para este serviço está disponível nesse horário.",
        )

    candidatos.sort(key=lambda item: item[0])
    return candidatos[0][1]
