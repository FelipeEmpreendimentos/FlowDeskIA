from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.database import get_db
from app.models.internal_chat import LeituraChatInterno, MensagemChatInterno
from app.models.models import Usuario
from app.schemas.internal_chat import (
    ChatInternoAutorOut,
    ChatInternoLeituraOut,
    ChatInternoMensagemCreate,
    ChatInternoMensagemOut,
    ChatInternoResumoOut,
)
from app.services.db_utils import commit_or_conflict


router = APIRouter(prefix="/chat-interno", tags=["Chat interno"])


def _mensagem_out(
    mensagem: MensagemChatInterno,
    autor: Usuario,
) -> ChatInternoMensagemOut:
    return ChatInternoMensagemOut(
        id=mensagem.id,
        conteudo=mensagem.conteudo,
        created_at=mensagem.created_at,
        autor=ChatInternoAutorOut(
            id=autor.id,
            nome=autor.nome,
            cargo=autor.cargo,
            foto_perfil=autor.foto_perfil,
        ),
    )


def _ultima_mensagem_empresa(db: Session, empresa_id: int) -> int | None:
    return db.scalar(
        select(func.max(MensagemChatInterno.id)).where(
            MensagemChatInterno.empresa_id == empresa_id
        )
    )


@router.get("/resumo", response_model=ChatInternoResumoOut)
def obter_resumo(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatInternoResumoOut:
    leitura = db.scalar(
        select(LeituraChatInterno).where(
            LeituraChatInterno.empresa_id == current_user.empresa_id,
            LeituraChatInterno.usuario_id == current_user.id,
        )
    )
    ultima_lida = leitura.ultima_mensagem_id if leitura else 0
    ultima_mensagem_id = _ultima_mensagem_empresa(db, current_user.empresa_id)

    nao_lidas = db.scalar(
        select(func.count(MensagemChatInterno.id)).where(
            MensagemChatInterno.empresa_id == current_user.empresa_id,
            MensagemChatInterno.id > ultima_lida,
            MensagemChatInterno.usuario_id != current_user.id,
        )
    )

    return ChatInternoResumoOut(
        nao_lidas=int(nao_lidas or 0),
        ultima_mensagem_id=ultima_mensagem_id,
    )


@router.post("/marcar-lido", response_model=ChatInternoLeituraOut)
def marcar_como_lido(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatInternoLeituraOut:
    ultima_mensagem_id = _ultima_mensagem_empresa(db, current_user.empresa_id) or 0
    leitura = db.scalar(
        select(LeituraChatInterno).where(
            LeituraChatInterno.empresa_id == current_user.empresa_id,
            LeituraChatInterno.usuario_id == current_user.id,
        )
    )

    agora = datetime.now(timezone.utc)
    if leitura is None:
        leitura = LeituraChatInterno(
            empresa_id=current_user.empresa_id,
            usuario_id=current_user.id,
            ultima_mensagem_id=ultima_mensagem_id,
            updated_at=agora,
        )
        db.add(leitura)
    else:
        leitura.ultima_mensagem_id = max(
            leitura.ultima_mensagem_id,
            ultima_mensagem_id,
        )
        leitura.updated_at = agora

    commit_or_conflict(db, leitura)
    return ChatInternoLeituraOut(
        ultima_mensagem_id=leitura.ultima_mensagem_id,
        updated_at=leitura.updated_at,
    )


@router.get("/mensagens", response_model=list[ChatInternoMensagemOut])
def listar_mensagens(
    antes_de_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=120, ge=1, le=300),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatInternoMensagemOut]:
    query = (
        select(MensagemChatInterno, Usuario)
        .join(Usuario, Usuario.id == MensagemChatInterno.usuario_id)
        .where(
            MensagemChatInterno.empresa_id == current_user.empresa_id,
            Usuario.empresa_id == current_user.empresa_id,
        )
    )

    if antes_de_id is not None:
        query = query.where(MensagemChatInterno.id < antes_de_id)

    rows = db.execute(
        query.order_by(MensagemChatInterno.id.desc()).limit(limit)
    ).all()

    return [
        _mensagem_out(mensagem, autor)
        for mensagem, autor in reversed(rows)
    ]


@router.post(
    "/mensagens",
    response_model=ChatInternoMensagemOut,
    status_code=status.HTTP_201_CREATED,
)
def enviar_mensagem(
    data: ChatInternoMensagemCreate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatInternoMensagemOut:
    conteudo = data.conteudo.strip()
    if not conteudo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Digite uma mensagem antes de enviar.",
        )

    mensagem = MensagemChatInterno(
        empresa_id=current_user.empresa_id,
        usuario_id=current_user.id,
        conteudo=conteudo,
    )
    db.add(mensagem)
    commit_or_conflict(db, mensagem)

    return _mensagem_out(mensagem, current_user)
