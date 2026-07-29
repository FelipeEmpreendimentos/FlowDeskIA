from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import (
    Cliente,
    Servico,
    Usuario,
    Veiculo,
)


def require_client(db: Session, empresa_id: int, cliente_id: int) -> Cliente:
    cliente = db.scalar(
        select(Cliente).where(
            Cliente.id == cliente_id,
            Cliente.empresa_id == empresa_id,
        )
    )
    if cliente is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente não encontrado.")
    return cliente


def require_user(db: Session, empresa_id: int, usuario_id: int) -> Usuario:
    usuario = db.scalar(
        select(Usuario).where(
            Usuario.id == usuario_id,
            Usuario.empresa_id == empresa_id,
        )
    )
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado.")
    return usuario


def require_service(db: Session, empresa_id: int, servico_id: int) -> Servico:
    servico = db.scalar(
        select(Servico).where(
            Servico.id == servico_id,
            Servico.empresa_id == empresa_id,
        )
    )
    if servico is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Serviço não encontrado.")
    return servico


def require_vehicle(db: Session, empresa_id: int, veiculo_id: int) -> Veiculo:
    veiculo = db.scalar(
        select(Veiculo)
        .join(Cliente, Cliente.id == Veiculo.cliente_id)
        .where(
            Veiculo.id == veiculo_id,
            Cliente.empresa_id == empresa_id,
        )
    )
    if veiculo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Veículo não encontrado.")
    return veiculo
