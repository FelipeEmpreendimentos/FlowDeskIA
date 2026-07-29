from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.database.database import get_db
from app.models.enums import CargoUsuario
from app.models.models import Servico, ServicoAdicionalVeiculo, Usuario
from app.schemas.entities import ServicoCreate, ServicoOut, ServicoUpdate
from app.services.audit import add_audit_log
from app.services.db_utils import apply_patch, commit_or_conflict
from app.services.ownership import require_service

router = APIRouter(prefix="/servicos", tags=["Serviços"])


def _sincronizar_adicionais(
    servico: Servico,
    adicionais: list[dict],
) -> None:
    """Atualiza adicionais sem recriar registros que já existem.

    A substituição direta da coleção fazia o SQLAlchemy tentar inserir os
    novos registros antes de remover os antigos. Como existe uma restrição
    única por serviço e tipo de veículo, a segunda edição podia gerar conflito.
    """
    por_tipo = {
        item["tipo_veiculo"]: item["valor_adicional"]
        for item in adicionais
    }
    existentes = {
        adicional.tipo_veiculo: adicional
        for adicional in servico.adicionais
    }

    # Remove somente os tipos que deixaram de ser enviados.
    for tipo_veiculo, adicional in list(existentes.items()):
        if tipo_veiculo not in por_tipo:
            servico.adicionais.remove(adicional)

    # Atualiza os registros existentes e cria apenas os que ainda não existem.
    for tipo_veiculo, valor in por_tipo.items():
        adicional = existentes.get(tipo_veiculo)

        if adicional is None:
            servico.adicionais.append(
                ServicoAdicionalVeiculo(
                    tipo_veiculo=tipo_veiculo,
                    valor_adicional=valor,
                )
            )
        else:
            adicional.valor_adicional = valor


@router.get("", response_model=list[ServicoOut])
def listar_servicos(
    ativo: bool | None = True,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Servico]:
    query = select(Servico).where(Servico.empresa_id == current_user.empresa_id)
    if ativo is not None:
        query = query.where(Servico.ativo == ativo)
    return list(db.scalars(query.order_by(Servico.nome).offset(offset).limit(limit)))


@router.post("", response_model=ServicoOut, status_code=status.HTTP_201_CREATED)
def criar_servico(
    data: ServicoCreate,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> Servico:
    values = data.model_dump(exclude={"adicionais"})
    servico = Servico(empresa_id=current_user.empresa_id, **values)
    _sincronizar_adicionais(
        servico,
        [item.model_dump() for item in data.adicionais],
    )
    db.add(servico)
    db.flush()
    add_audit_log(
        db,
        user=current_user,
        action="CRIOU_SERVICO",
        entity="servicos",
        entity_id=servico.id,
        details={
            "adicional_por_tipo_ativo": servico.adicional_por_tipo_ativo,
        },
    )
    return commit_or_conflict(db, servico)


@router.get("/{servico_id}", response_model=ServicoOut)
def obter_servico(
    servico_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Servico:
    return require_service(db, current_user.empresa_id, servico_id)


@router.patch("/{servico_id}", response_model=ServicoOut)
def atualizar_servico(
    servico_id: int,
    data: ServicoUpdate,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> Servico:
    servico = require_service(db, current_user.empresa_id, servico_id)
    values = data.model_dump(exclude_unset=True)
    adicionais = values.pop("adicionais", None)
    apply_patch(servico, values)
    if adicionais is not None:
        _sincronizar_adicionais(servico, adicionais)
    add_audit_log(
        db,
        user=current_user,
        action="ATUALIZOU_SERVICO",
        entity="servicos",
        entity_id=servico.id,
        details={
            "adicional_por_tipo_ativo": servico.adicional_por_tipo_ativo,
        },
    )
    return commit_or_conflict(db, servico)


@router.delete("/{servico_id}", status_code=status.HTTP_204_NO_CONTENT)
def desativar_servico(
    servico_id: int,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> Response:
    servico = require_service(db, current_user.empresa_id, servico_id)
    servico.ativo = False
    add_audit_log(
        db,
        user=current_user,
        action="DESATIVOU_SERVICO",
        entity="servicos",
        entity_id=servico.id,
    )
    commit_or_conflict(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
