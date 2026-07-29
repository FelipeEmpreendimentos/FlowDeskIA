from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.database import get_db
from app.models.enums import RemetenteMensagem, StatusConversa
from app.models.models import Conversa, Mensagem, Usuario
from app.schemas.entities import (
    ConversaAvaliacaoResposta,
    ConversaCreate,
    ConversaFinalizar,
    ConversaOut,
    ConversaUpdate,
    MensagemCreate,
    MensagemOut,
    UsuarioOut,
)
from app.services.audit import add_audit_log
from app.services.db_utils import apply_patch, commit_or_conflict
from app.services.ownership import require_client, require_user

router = APIRouter(prefix="/conversas", tags=["Conversas"])


def _get(db: Session, empresa_id: int, conversa_id: int) -> Conversa:
    item = db.scalar(
        select(Conversa).where(
            Conversa.id == conversa_id,
            Conversa.empresa_id == empresa_id,
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversa não encontrada.")
    return item


def _limpar_finalizacao(item: Conversa) -> None:
    item.finalizada_em = None
    item.finalizada_por_id = None
    item.resumo_finalizacao = None


def _limpar_avaliacao_pendente(item: Conversa) -> None:
    if item.avaliacao_nota is not None:
        return
    item.avaliacao_solicitada = False
    item.avaliacao_token = None
    item.avaliacao_enviada_em = None
    item.avaliacao_comentario = None
    item.avaliacao_respondida_em = None


@router.get("", response_model=list[ConversaOut])
def listar_conversas(
    status_conversa: StatusConversa | None = None,
    grupo: Literal["ATUAIS", "HISTORICO"] | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Conversa]:
    query = select(Conversa).where(
        Conversa.empresa_id == current_user.empresa_id
    )

    if grupo == "ATUAIS":
        query = query.where(
            Conversa.status.in_(
                [StatusConversa.ABERTA, StatusConversa.EM_ATENDIMENTO]
            )
        )
    elif grupo == "HISTORICO":
        query = query.where(Conversa.status == StatusConversa.FINALIZADA)
    elif status_conversa:
        query = query.where(Conversa.status == status_conversa)

    if grupo == "HISTORICO":
        query = query.order_by(
            Conversa.finalizada_em.desc().nullslast(),
            Conversa.ultima_interacao.desc().nullslast(),
        )
    else:
        query = query.order_by(
            Conversa.ultima_interacao.desc().nullslast(),
            Conversa.created_at.desc(),
        )

    return list(db.scalars(query.offset(offset).limit(limit)))


@router.post("", response_model=ConversaOut, status_code=status.HTTP_201_CREATED)
def criar_conversa(
    data: ConversaCreate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversa:
    require_client(db, current_user.empresa_id, data.cliente_id)
    if data.responsavel_id:
        require_user(db, current_user.empresa_id, data.responsavel_id)

    item = Conversa(
        empresa_id=current_user.empresa_id,
        **data.model_dump(),
    )

    if data.responsavel_id:
        item.status = StatusConversa.EM_ATENDIMENTO
        item.ia_ativa = False

    db.add(item)
    db.flush()
    add_audit_log(
        db,
        user=current_user,
        action="CRIOU_CONVERSA",
        entity="conversas",
        entity_id=item.id,
    )
    return commit_or_conflict(db, item)


@router.get("/responsaveis", response_model=list[UsuarioOut])
def listar_responsaveis(
    ativo: bool | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Usuario]:
    query = select(Usuario).where(
        Usuario.empresa_id == current_user.empresa_id
    )
    if ativo is not None:
        query = query.where(Usuario.ativo == ativo)
    return list(
        db.scalars(query.order_by(Usuario.nome).offset(offset).limit(limit))
    )


@router.get("/{conversa_id}", response_model=ConversaOut)
def obter_conversa(
    conversa_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversa:
    return _get(db, current_user.empresa_id, conversa_id)


@router.patch("/{conversa_id}", response_model=ConversaOut)
def atualizar_conversa(
    conversa_id: int,
    data: ConversaUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversa:
    item = _get(db, current_user.empresa_id, conversa_id)
    values = data.model_dump(exclude_unset=True)

    if item.status == StatusConversa.FINALIZADA:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Reabra a conversa antes de alterar seus dados.",
        )

    if values.get("status") == StatusConversa.FINALIZADA:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Use a opção Finalizar conversa para confirmar essa ação.",
        )

    if "responsavel_id" in values and values["responsavel_id"] is not None:
        require_user(
            db,
            current_user.empresa_id,
            values["responsavel_id"],
        )
        values["ia_ativa"] = False
        values["status"] = StatusConversa.EM_ATENDIMENTO

    if values.get("status") == StatusConversa.EM_ATENDIMENTO:
        if item.responsavel_id is None and "responsavel_id" not in values:
            values["responsavel_id"] = current_user.id
        values["ia_ativa"] = False

    if values.get("status") == StatusConversa.ABERTA:
        values["responsavel_id"] = None
        values.setdefault("ia_ativa", True)

    apply_patch(item, values)
    add_audit_log(
        db,
        user=current_user,
        action="ATUALIZOU_CONVERSA",
        entity="conversas",
        entity_id=item.id,
        details={"campos": sorted(values.keys())},
    )
    return commit_or_conflict(db, item)


@router.post("/{conversa_id}/finalizar", response_model=ConversaOut)
def finalizar_conversa(
    conversa_id: int,
    data: ConversaFinalizar,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversa:
    item = _get(db, current_user.empresa_id, conversa_id)
    if item.status == StatusConversa.FINALIZADA:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Essa conversa já está finalizada.",
        )

    agora = datetime.now(timezone.utc)
    item.status = StatusConversa.FINALIZADA
    item.ia_ativa = False
    item.finalizada_em = agora
    item.finalizada_por_id = current_user.id
    item.responsavel_id = item.responsavel_id or current_user.id
    item.resumo_finalizacao = (
        data.resumo_finalizacao.strip()
        if data.resumo_finalizacao and data.resumo_finalizacao.strip()
        else None
    )

    item.avaliacao_solicitada = data.enviar_avaliacao
    item.avaliacao_enviada_em = None
    item.avaliacao_nota = None
    item.avaliacao_comentario = None
    item.avaliacao_respondida_em = None
    item.avaliacao_token = str(uuid4()) if data.enviar_avaliacao else None

    add_audit_log(
        db,
        user=current_user,
        action="FINALIZOU_CONVERSA",
        entity="conversas",
        entity_id=item.id,
        details={"avaliacao_solicitada": data.enviar_avaliacao},
    )
    return commit_or_conflict(db, item)


@router.post("/{conversa_id}/reabrir", response_model=ConversaOut)
def reabrir_conversa(
    conversa_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversa:
    item = _get(db, current_user.empresa_id, conversa_id)
    if item.status != StatusConversa.FINALIZADA:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Somente conversas finalizadas podem ser reabertas.",
        )

    item.status = StatusConversa.EM_ATENDIMENTO
    item.responsavel_id = current_user.id
    item.ia_ativa = False
    _limpar_finalizacao(item)
    _limpar_avaliacao_pendente(item)

    add_audit_log(
        db,
        user=current_user,
        action="REABRIU_CONVERSA",
        entity="conversas",
        entity_id=item.id,
    )
    return commit_or_conflict(db, item)


@router.patch("/{conversa_id}/avaliacao", response_model=ConversaOut)
def registrar_avaliacao(
    conversa_id: int,
    data: ConversaAvaliacaoResposta,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversa:
    item = _get(db, current_user.empresa_id, conversa_id)
    if not item.avaliacao_solicitada:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Essa conversa não possui uma avaliação solicitada.",
        )

    item.avaliacao_nota = data.nota
    item.avaliacao_comentario = (
        data.comentario.strip()
        if data.comentario and data.comentario.strip()
        else None
    )
    item.avaliacao_respondida_em = datetime.now(timezone.utc)

    add_audit_log(
        db,
        user=current_user,
        action="REGISTROU_AVALIACAO_CONVERSA",
        entity="conversas",
        entity_id=item.id,
        details={"nota": data.nota},
    )
    return commit_or_conflict(db, item)


@router.get("/{conversa_id}/mensagens", response_model=list[MensagemOut])
def listar_mensagens(
    conversa_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=300),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Mensagem]:
    _get(db, current_user.empresa_id, conversa_id)
    return list(
        db.scalars(
            select(Mensagem)
            .where(Mensagem.conversa_id == conversa_id)
            .order_by(Mensagem.data_envio)
            .offset(offset)
            .limit(limit)
        )
    )


@router.post(
    "/{conversa_id}/mensagens",
    response_model=MensagemOut,
    status_code=status.HTTP_201_CREATED,
)
def criar_mensagem(
    conversa_id: int,
    data: MensagemCreate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Mensagem:
    conversation = _get(db, current_user.empresa_id, conversa_id)

    message = Mensagem(
        conversa_id=conversa_id,
        **data.model_dump(),
    )
    db.add(message)
    db.flush()

    agora = datetime.now(timezone.utc)
    conversation.ultima_mensagem_id = message.id
    conversation.ultima_interacao = agora

    if data.remetente in (
        RemetenteMensagem.FUNCIONARIO,
        RemetenteMensagem.GERENTE,
    ):
        conversation.status = StatusConversa.EM_ATENDIMENTO
        conversation.responsavel_id = current_user.id
        conversation.ia_ativa = False
    elif data.remetente == RemetenteMensagem.CLIENTE:
        if conversation.status == StatusConversa.FINALIZADA:
            conversation.status = StatusConversa.ABERTA
            conversation.responsavel_id = None
            conversation.ia_ativa = True
            _limpar_finalizacao(conversation)
            _limpar_avaliacao_pendente(conversation)
    elif data.remetente == RemetenteMensagem.IA:
        conversation.ia_ativa = True

    add_audit_log(
        db,
        user=current_user,
        action="ENVIOU_MENSAGEM",
        entity="mensagens",
        entity_id=message.id,
    )
    return commit_or_conflict(
        db,
        message,
        "Essa mensagem do WhatsApp já foi registrada.",
    )


@router.patch("/{conversa_id}/mensagens/{mensagem_id}/lida", response_model=MensagemOut)
def marcar_mensagem_lida(
    conversa_id: int,
    mensagem_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Mensagem:
    _get(db, current_user.empresa_id, conversa_id)
    message = db.scalar(
        select(Mensagem).where(
            Mensagem.id == mensagem_id,
            Mensagem.conversa_id == conversa_id,
        )
    )
    if message is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mensagem não encontrada.")
    message.lida = True
    return commit_or_conflict(db, message)
