from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.database.database import get_db
from app.models.enums import CargoUsuario
from app.models.models import (
    Cliente,
    ConfigIA,
    Integracao,
    MemoriaIA,
    Usuario,
)
from app.schemas.entities import (
    ConfigIAOut,
    ConfigIAPut,
    IntegracaoCreate,
    IntegracaoOut,
    IntegracaoUpdate,
    MemoriaCreate,
    MemoriaOut,
    MemoriaUpdate,
)
from app.services.audit import add_audit_log
from app.services.db_utils import apply_patch, commit_or_conflict
from app.services.ownership import require_client

router = APIRouter(prefix="/configuracoes", tags=["Configurações"])


@router.get("/ia", response_model=ConfigIAOut | None)
def obter_config_ia(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConfigIA | None:
    return db.scalar(
        select(ConfigIA).where(ConfigIA.empresa_id == current_user.empresa_id)
    )


@router.put("/ia", response_model=ConfigIAOut)
def salvar_config_ia(
    data: ConfigIAPut,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> ConfigIA:
    item = db.scalar(
        select(ConfigIA).where(ConfigIA.empresa_id == current_user.empresa_id)
    )
    if item is None:
        item = ConfigIA(
            empresa_id=current_user.empresa_id,
            **data.model_dump(),
        )
        db.add(item)
        db.flush()
    else:
        apply_patch(item, data.model_dump())

    add_audit_log(
        db,
        user=current_user,
        action="ATUALIZOU_CONFIG_IA",
        entity="config_ia",
        entity_id=item.id,
    )
    return commit_or_conflict(db, item)


@router.get("/memorias", response_model=list[MemoriaOut])
def listar_memorias(
    cliente_id: int | None = None,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MemoriaIA]:
    query = select(MemoriaIA).where(
        MemoriaIA.empresa_id == current_user.empresa_id
    )
    if cliente_id:
        query = query.where(MemoriaIA.cliente_id == cliente_id)
    return list(db.scalars(query.order_by(MemoriaIA.updated_at.desc())))


@router.post(
    "/memorias",
    response_model=MemoriaOut,
    status_code=status.HTTP_201_CREATED,
)
def criar_memoria(
    data: MemoriaCreate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemoriaIA:
    require_client(db, current_user.empresa_id, data.cliente_id)
    item = MemoriaIA(
        empresa_id=current_user.empresa_id,
        **data.model_dump(),
    )
    db.add(item)
    return commit_or_conflict(db, item)


@router.patch("/memorias/{memoria_id}", response_model=MemoriaOut)
def atualizar_memoria(
    memoria_id: int,
    data: MemoriaUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemoriaIA:
    item = db.scalar(
        select(MemoriaIA).where(
            MemoriaIA.id == memoria_id,
            MemoriaIA.empresa_id == current_user.empresa_id,
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memória não encontrada.")
    apply_patch(item, data.model_dump(exclude_unset=True))
    return commit_or_conflict(db, item)


@router.delete("/memorias/{memoria_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_memoria(
    memoria_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    item = db.scalar(
        select(MemoriaIA).where(
            MemoriaIA.id == memoria_id,
            MemoriaIA.empresa_id == current_user.empresa_id,
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memória não encontrada.")
    db.delete(item)
    commit_or_conflict(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/integracoes", response_model=list[IntegracaoOut])
def listar_integracoes(
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> list[Integracao]:
    return list(
        db.scalars(
            select(Integracao).where(
                Integracao.empresa_id == current_user.empresa_id
            )
        )
    )


@router.post(
    "/integracoes",
    response_model=IntegracaoOut,
    status_code=status.HTTP_201_CREATED,
)
def criar_integracao(
    data: IntegracaoCreate,
    current_user: Usuario = Depends(require_roles(CargoUsuario.ADMIN)),
    db: Session = Depends(get_db),
) -> Integracao:
    item = Integracao(
        empresa_id=current_user.empresa_id,
        **data.model_dump(),
    )
    db.add(item)
    db.flush()
    add_audit_log(
        db,
        user=current_user,
        action="CRIOU_INTEGRACAO",
        entity="integracoes",
        entity_id=item.id,
    )
    return commit_or_conflict(
        db,
        item,
        "Já existe uma integração desse tipo para a empresa.",
    )


@router.patch("/integracoes/{integracao_id}", response_model=IntegracaoOut)
def atualizar_integracao(
    integracao_id: int,
    data: IntegracaoUpdate,
    current_user: Usuario = Depends(require_roles(CargoUsuario.ADMIN)),
    db: Session = Depends(get_db),
) -> Integracao:
    item = db.scalar(
        select(Integracao).where(
            Integracao.id == integracao_id,
            Integracao.empresa_id == current_user.empresa_id,
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Integração não encontrada.")
    apply_patch(item, data.model_dump(exclude_unset=True))
    add_audit_log(
        db,
        user=current_user,
        action="ATUALIZOU_INTEGRACAO",
        entity="integracoes",
        entity_id=item.id,
    )
    return commit_or_conflict(db, item)
