from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.permissions import is_management
from app.database.database import get_db
from app.models.enums import CargoUsuario, RemetenteMensagem, StatusConversa
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
from app.services.notifications import notify_management, notify_user
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


def _conversa_ativa_existente(
    db: Session,
    *,
    empresa_id: int,
    cliente_id: int,
    origem,
) -> Conversa | None:
    return db.scalar(
        select(Conversa)
        .where(
            Conversa.empresa_id == empresa_id,
            Conversa.cliente_id == cliente_id,
            Conversa.origem == origem,
            Conversa.status.in_(
                [StatusConversa.ABERTA, StatusConversa.EM_ATENDIMENTO]
            ),
        )
        .order_by(
            Conversa.ultima_interacao.desc().nullslast(),
            Conversa.created_at.desc(),
        )
    )


def _ensure_access(item: Conversa, current_user: Usuario) -> None:
    if is_management(current_user):
        return

    if item.responsavel_id == current_user.id:
        return

    if item.responsavel_id is None and item.status == StatusConversa.ABERTA:
        return

    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        "Você só pode acessar conversas atribuídas a você ou ainda sem responsável.",
    )


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

    if not is_management(current_user):
        query = query.where(
            or_(
                Conversa.responsavel_id == current_user.id,
                (
                    Conversa.responsavel_id.is_(None)
                    & (Conversa.status == StatusConversa.ABERTA)
                ),
            )
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

    existente = _conversa_ativa_existente(
        db,
        empresa_id=current_user.empresa_id,
        cliente_id=data.cliente_id,
        origem=data.origem,
    )
    if existente is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            (
                f"Já existe uma conversa ativa deste cliente no canal "
                f"{data.origem.value if hasattr(data.origem, 'value') else data.origem} "
                f"(conversa #{existente.id}). Abra a conversa existente para continuar o atendimento."
            ),
        )

    values = data.model_dump()

    if not is_management(current_user):
        if values.get("responsavel_id") not in (None, current_user.id):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Funcionários podem atribuir novas conversas somente a si mesmos.",
            )
        values["responsavel_id"] = current_user.id

    if values.get("responsavel_id"):
        require_user(
            db,
            current_user.empresa_id,
            values["responsavel_id"],
        )

    item = Conversa(
        empresa_id=current_user.empresa_id,
        **values,
    )

    if item.responsavel_id:
        item.status = StatusConversa.EM_ATENDIMENTO
        item.ia_ativa = False

    db.add(item)
    db.flush()

    if item.responsavel_id and item.responsavel_id != current_user.id:
        notify_user(
            db,
            empresa_id=current_user.empresa_id,
            usuario_id=item.responsavel_id,
            titulo="Nova conversa atribuída",
            mensagem=f"A conversa #{item.id} foi atribuída a você.",
        )
    elif item.responsavel_id is None:
        notify_management(
            db,
            empresa_id=current_user.empresa_id,
            titulo="Nova conversa sem responsável",
            mensagem=f"A conversa #{item.id} aguarda um atendente.",
            exclude_user_ids=(current_user.id,),
        )

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
    if not is_management(current_user):
        query = query.where(Usuario.id == current_user.id)
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
    item = _get(db, current_user.empresa_id, conversa_id)
    _ensure_access(item, current_user)
    return item


@router.patch("/{conversa_id}", response_model=ConversaOut)
def atualizar_conversa(
    conversa_id: int,
    data: ConversaUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversa:
    item = _get(db, current_user.empresa_id, conversa_id)
    _ensure_access(item, current_user)
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

    old_responsible_id = item.responsavel_id

    if not is_management(current_user):
        if values.get("responsavel_id") not in (None, current_user.id):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Funcionários não podem transferir conversas para outro usuário.",
            )
        if values.get("status") == StatusConversa.ABERTA:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Somente a gestão pode devolver uma conversa para a fila.",
            )
        if "ia_ativa" in values:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Funcionários não podem alterar o controle da IA.",
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

    if (
        item.responsavel_id
        and item.responsavel_id != old_responsible_id
        and item.responsavel_id != current_user.id
    ):
        notify_user(
            db,
            empresa_id=current_user.empresa_id,
            usuario_id=item.responsavel_id,
            titulo="Nova conversa atribuída",
            mensagem=f"A conversa #{item.id} foi atribuída a você.",
        )

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
    _ensure_access(item, current_user)
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
    _ensure_access(item, current_user)
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
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
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
    item = _get(db, current_user.empresa_id, conversa_id)
    _ensure_access(item, current_user)
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
    _ensure_access(conversation, current_user)

    if (
        current_user.cargo == CargoUsuario.FUNCIONARIO
        and data.remetente != RemetenteMensagem.FUNCIONARIO
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Funcionários só podem enviar mensagens como funcionário.",
        )

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

        if conversation.responsavel_id:
            notify_user(
                db,
                empresa_id=current_user.empresa_id,
                usuario_id=conversation.responsavel_id,
                titulo="Nova mensagem de cliente",
                mensagem=f"A conversa #{conversation.id} recebeu uma nova mensagem.",
            )
        else:
            notify_management(
                db,
                empresa_id=current_user.empresa_id,
                titulo="Cliente aguardando atendimento",
                mensagem=f"A conversa #{conversation.id} recebeu uma nova mensagem.",
                exclude_user_ids=(current_user.id,),
            )
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
    conversation = _get(db, current_user.empresa_id, conversa_id)
    _ensure_access(conversation, current_user)
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
