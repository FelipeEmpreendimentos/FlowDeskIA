from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.database.database import get_db
from app.models.enums import CargoUsuario, StatusCliente
from app.models.models import Cliente, Usuario
from app.schemas.entities import ClienteCreate, ClienteOut, ClienteUpdate
from app.services.audit import add_audit_log
from app.services.db_utils import apply_patch, commit_or_conflict
from app.services.ownership import require_client
from app.services.plans import enforce_limit

router = APIRouter(prefix="/clientes", tags=["Clientes"])


@router.get("", response_model=list[ClienteOut])
def listar_clientes(
    busca: str | None = None,
    campo_busca: Literal["todos", "nome", "telefone", "email"] = "todos",
    status_cliente: StatusCliente | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Cliente]:
    query = select(Cliente).where(Cliente.empresa_id == current_user.empresa_id)

    if busca:
        term = f"%{busca.strip()}%"
        if campo_busca == "nome":
            query = query.where(Cliente.nome.ilike(term))
        elif campo_busca == "telefone":
            query = query.where(
                or_(Cliente.telefone.ilike(term), Cliente.whatsapp.ilike(term))
            )
        elif campo_busca == "email":
            query = query.where(Cliente.email.ilike(term))
        else:
            query = query.where(
                or_(
                    Cliente.nome.ilike(term),
                    Cliente.telefone.ilike(term),
                    Cliente.whatsapp.ilike(term),
                    Cliente.email.ilike(term),
                )
            )
    if status_cliente:
        query = query.where(Cliente.status == status_cliente)

    return list(db.scalars(query.order_by(Cliente.nome).offset(offset).limit(limit)))


@router.post("", response_model=ClienteOut, status_code=status.HTTP_201_CREATED)
def criar_cliente(
    data: ClienteCreate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Cliente:
    enforce_limit(db, current_user.empresa_id, "clientes")
    cliente = Cliente(empresa_id=current_user.empresa_id, **data.model_dump())
    db.add(cliente)
    db.flush()
    add_audit_log(
        db,
        user=current_user,
        action="CRIOU_CLIENTE",
        entity="clientes",
        entity_id=cliente.id,
    )
    return commit_or_conflict(db, cliente)


@router.get("/{cliente_id}", response_model=ClienteOut)
def obter_cliente(
    cliente_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Cliente:
    return require_client(db, current_user.empresa_id, cliente_id)


@router.patch("/{cliente_id}", response_model=ClienteOut)
def atualizar_cliente(
    cliente_id: int,
    data: ClienteUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Cliente:
    cliente = require_client(db, current_user.empresa_id, cliente_id)
    values = data.model_dump(exclude_unset=True)

    if current_user.cargo == CargoUsuario.FUNCIONARIO and "status" in values:
        if values["status"] == cliente.status:
            # O formulário compartilhado pode reenviar o status atual mesmo
            # quando o funcionário editou apenas os dados operacionais.
            values.pop("status")
        else:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Funcionários não podem alterar o status de clientes.",
            )
    if values.get("status") == StatusCliente.ATIVO and cliente.status == StatusCliente.INATIVO:
        enforce_limit(db, current_user.empresa_id, "clientes")

    apply_patch(cliente, values)
    add_audit_log(
        db,
        user=current_user,
        action="ATUALIZOU_CLIENTE",
        entity="clientes",
        entity_id=cliente.id,
    )
    return commit_or_conflict(db, cliente)


@router.delete("/{cliente_id}", status_code=status.HTTP_204_NO_CONTENT)
def desativar_cliente(
    cliente_id: int,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> Response:
    cliente = require_client(db, current_user.empresa_id, cliente_id)
    cliente.status = StatusCliente.INATIVO
    add_audit_log(
        db,
        user=current_user,
        action="DESATIVOU_CLIENTE",
        entity="clientes",
        entity_id=cliente.id,
    )
    commit_or_conflict(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
