from datetime import date, time

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.database.database import get_db
from app.models.enums import CargoUsuario
from app.models.models import Usuario
from app.schemas.agenda_availability import SlotDisponivelDetalhado
from app.services.agenda import add_minutes, available_slots
from app.services.ownership import require_service, require_user
from app.services.service_assignment import (
    ensure_employee_qualified,
    qualification_map,
    save_service_qualification,
    smart_available_slots,
    smart_employee_for_slot,
)


router = APIRouter(tags=["Agenda inteligente"])


class QualificacaoServicoOut(BaseModel):
    servico_id: int
    funcionario_ids: list[int]


class QualificacaoServicoUpdate(BaseModel):
    funcionario_ids: list[int] = Field(min_length=1)


@router.get(
    "/servicos-qualificacoes",
    response_model=list[QualificacaoServicoOut],
)
def listar_qualificacoes(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[QualificacaoServicoOut]:
    mapa = qualification_map(db, empresa_id=current_user.empresa_id)
    return [
        QualificacaoServicoOut(
            servico_id=servico_id,
            funcionario_ids=funcionario_ids,
        )
        for servico_id, funcionario_ids in mapa.items()
    ]


@router.put(
    "/servicos/{servico_id}/funcionarios",
    response_model=QualificacaoServicoOut,
)
def atualizar_qualificacao(
    servico_id: int,
    data: QualificacaoServicoUpdate,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> QualificacaoServicoOut:
    require_service(db, current_user.empresa_id, servico_id)
    funcionario_ids = save_service_qualification(
        db,
        empresa_id=current_user.empresa_id,
        servico_id=servico_id,
        funcionario_ids=data.funcionario_ids,
    )
    return QualificacaoServicoOut(
        servico_id=servico_id,
        funcionario_ids=funcionario_ids,
    )


# Esta rota entra antes da rota legada de Agenda. Assim o frontend atual passa
# a receber a nova distribuição sem precisar manter duas regras de negócio.
@router.get(
    "/agendamentos/disponibilidade",
    response_model=list[SlotDisponivelDetalhado],
)
def consultar_disponibilidade_inteligente(
    data: date,
    servico_id: int,
    funcionario_id: int | None = None,
    intervalo_minutos: int = Query(30, ge=5, le=240),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SlotDisponivelDetalhado]:
    servico = require_service(db, current_user.empresa_id, servico_id)

    if funcionario_id is not None:
        funcionario = require_user(db, current_user.empresa_id, funcionario_id)
        ensure_employee_qualified(
            db,
            empresa_id=current_user.empresa_id,
            servico_id=servico.id,
            funcionario_id=funcionario.id,
        )
        slots = available_slots(
            db,
            empresa_id=current_user.empresa_id,
            target_date=data,
            funcionario_id=funcionario.id,
            service=servico,
            interval_minutes=intervalo_minutos,
        )
        return [
            SlotDisponivelDetalhado(
                hora_inicio=start,
                hora_fim=end,
                funcionario_id=funcionario.id,
                funcionario_nome=funcionario.nome,
            )
            for start, end in slots
        ]

    slots = smart_available_slots(
        db,
        empresa_id=current_user.empresa_id,
        target_date=data,
        service=servico,
        interval_minutes=intervalo_minutos,
    )
    nomes = {
        item.id: item.nome
        for item in db.scalars(
            select(Usuario).where(
                Usuario.empresa_id == current_user.empresa_id,
                Usuario.ativo.is_(True),
            )
        )
    }
    return [
        SlotDisponivelDetalhado(
            hora_inicio=start,
            hora_fim=end,
            funcionario_id=funcionario_id,
            funcionario_nome=nomes.get(
                funcionario_id,
                f"Usuário #{funcionario_id}",
            ),
        )
        for start, end, funcionario_id in slots
    ]


class AtribuicaoAutomaticaOut(BaseModel):
    funcionario_id: int
    funcionario_nome: str
    hora_inicio: time
    hora_fim: time


@router.get(
    "/agendamentos/atribuicao-automatica",
    response_model=AtribuicaoAutomaticaOut,
)
def atribuir_funcionario_automaticamente(
    data: date,
    servico_id: int,
    hora_inicio: time,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AtribuicaoAutomaticaOut:
    """Ponto único para a futura IA/WhatsApp usar a mesma regra do portal."""
    servico = require_service(db, current_user.empresa_id, servico_id)
    hora_fim = add_minutes(hora_inicio, servico.duracao_minutos)
    funcionario_id = smart_employee_for_slot(
        db,
        empresa_id=current_user.empresa_id,
        target_date=data,
        service=servico,
        start=hora_inicio,
        end=hora_fim,
    )
    funcionario = require_user(db, current_user.empresa_id, funcionario_id)
    return AtribuicaoAutomaticaOut(
        funcionario_id=funcionario.id,
        funcionario_nome=funcionario.nome,
        hora_inicio=hora_inicio,
        hora_fim=hora_fim,
    )
