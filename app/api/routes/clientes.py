from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.database.database import get_db
from app.models.enums import CargoUsuario, StatusCliente
from app.models.models import Agendamento, Cliente, Conversa, Usuario
from app.schemas.entities import ClienteCreate, ClienteOut, ClienteUpdate
from app.services.audit import add_audit_log
from app.services.db_utils import apply_patch, commit_or_conflict
from app.services.ownership import require_client
from app.services.plans import enforce_limit

router = APIRouter(prefix="/clientes", tags=["Clientes"])


def _garantir_nome_unico(
    db: Session,
    *,
    empresa_id: int,
    nome: str,
    ignorar_id: int | None = None,
) -> str:
    normalizado = nome.strip()
    query = select(Cliente.id).where(
        Cliente.empresa_id == empresa_id,
        func.lower(func.trim(Cliente.nome)) == normalizado.lower(),
    )
    if ignorar_id is not None:
        query = query.where(Cliente.id != ignorar_id)
    if db.scalar(query.limit(1)) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Já existe um cliente cadastrado com esse nome.",
        )
    return normalizado


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
    values = data.model_dump()
    values["nome"] = _garantir_nome_unico(
        db,
        empresa_id=current_user.empresa_id,
        nome=values["nome"],
    )
    cliente = Cliente(empresa_id=current_user.empresa_id, **values)
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

    if "nome" in values:
        nome_normalizado = values["nome"].strip()
        if nome_normalizado.lower() != cliente.nome.strip().lower():
            nome_normalizado = _garantir_nome_unico(
                db,
                empresa_id=current_user.empresa_id,
                nome=nome_normalizado,
                ignorar_id=cliente.id,
            )
        values["nome"] = nome_normalizado

    if current_user.cargo == CargoUsuario.FUNCIONARIO and "status" in values:
        if values["status"] == cliente.status:
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


@router.delete("/{cliente_id}/permanente", status_code=status.HTTP_204_NO_CONTENT)
def excluir_cliente_permanentemente(
    cliente_id: int,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> Response:
    cliente = require_client(db, current_user.empresa_id, cliente_id)

    possui_agendamento = db.scalar(
        select(Agendamento.id)
        .where(
            Agendamento.empresa_id == current_user.empresa_id,
            Agendamento.cliente_id == cliente.id,
        )
        .limit(1)
    )
    possui_conversa = db.scalar(
        select(Conversa.id)
        .where(
            Conversa.empresa_id == current_user.empresa_id,
            Conversa.cliente_id == cliente.id,
        )
        .limit(1)
    )

    if possui_agendamento is not None or possui_conversa is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Este cliente possui histórico de atendimentos ou conversas. Desative-o para preservar os registros.",
        )

    add_audit_log(
        db,
        user=current_user,
        action="EXCLUIU_CLIENTE",
        entity="clientes",
        entity_id=cliente.id,
        details={"nome": cliente.nome},
    )
    db.delete(cliente)
    commit_or_conflict(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
