from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.database.database import get_db
from app.models.enums import CargoUsuario
from app.models.models import Cliente, Usuario, Veiculo
from app.schemas.entities import VeiculoCreate, VeiculoOut, VeiculoUpdate
from app.services.audit import add_audit_log
from app.services.db_utils import apply_patch, commit_or_conflict
from app.services.ownership import require_client, require_vehicle

router = APIRouter(prefix="/veiculos", tags=["Veículos"])


@router.get("", response_model=list[VeiculoOut])
def listar_veiculos(
    cliente_id: int | None = None,
    busca: str | None = None,
    campo_busca: Literal[
        "todos", "cliente", "modelo", "apelido", "tipo"
    ] = "todos",
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Veiculo]:
    query = (
        select(Veiculo)
        .join(Cliente, Cliente.id == Veiculo.cliente_id)
        .where(Cliente.empresa_id == current_user.empresa_id)
    )
    if cliente_id is not None:
        query = query.where(Veiculo.cliente_id == cliente_id)

    if busca:
        term = f"%{busca.strip()}%"

        if campo_busca == "cliente":
            query = query.where(Cliente.nome.ilike(term))
        elif campo_busca == "modelo":
            query = query.where(Veiculo.modelo.ilike(term))
        elif campo_busca == "apelido":
            query = query.where(Veiculo.apelido.ilike(term))
        elif campo_busca == "tipo":
            query = query.where(Veiculo.tipo_veiculo.ilike(term))
        else:
            query = query.where(
                or_(
                    Cliente.nome.ilike(term),
                    Veiculo.modelo.ilike(term),
                    Veiculo.apelido.ilike(term),
                    Veiculo.tipo_veiculo.ilike(term),
                    Veiculo.marca.ilike(term),
                    Veiculo.placa.ilike(term),
                )
            )

    query = query.order_by(Cliente.nome, Veiculo.modelo, Veiculo.id)
    return list(db.scalars(query.offset(offset).limit(limit)))


@router.post("", response_model=VeiculoOut, status_code=status.HTTP_201_CREATED)
def criar_veiculo(
    data: VeiculoCreate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Veiculo:
    require_client(db, current_user.empresa_id, data.cliente_id)
    values = data.model_dump()
    if values.get("placa"):
        values["placa"] = values["placa"].upper().replace("-", "")
    veiculo = Veiculo(**values)
    db.add(veiculo)
    db.flush()
    add_audit_log(
        db,
        user=current_user,
        action="CRIOU_VEICULO",
        entity="veiculos",
        entity_id=veiculo.id,
    )
    return commit_or_conflict(db, veiculo)


@router.get("/{veiculo_id}", response_model=VeiculoOut)
def obter_veiculo(
    veiculo_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Veiculo:
    return require_vehicle(db, current_user.empresa_id, veiculo_id)


@router.patch("/{veiculo_id}", response_model=VeiculoOut)
def atualizar_veiculo(
    veiculo_id: int,
    data: VeiculoUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Veiculo:
    veiculo = require_vehicle(db, current_user.empresa_id, veiculo_id)
    values = data.model_dump(exclude_unset=True)
    if values.get("placa"):
        values["placa"] = values["placa"].upper().replace("-", "")
    apply_patch(veiculo, values)
    add_audit_log(
        db,
        user=current_user,
        action="ATUALIZOU_VEICULO",
        entity="veiculos",
        entity_id=veiculo.id,
    )
    return commit_or_conflict(db, veiculo)


@router.delete("/{veiculo_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_veiculo(
    veiculo_id: int,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> Response:
    veiculo = require_vehicle(db, current_user.empresa_id, veiculo_id)
    entity_id = veiculo.id
    db.delete(veiculo)
    add_audit_log(
        db,
        user=current_user,
        action="EXCLUIU_VEICULO",
        entity="veiculos",
        entity_id=entity_id,
    )
    commit_or_conflict(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
