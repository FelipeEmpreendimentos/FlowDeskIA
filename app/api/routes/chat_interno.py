from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.database import get_db
from app.models.internal_chat import (
    CanalChatInterno,
    LeituraChatInterno,
    MembroCanalChatInterno,
    MensagemChatInterno,
)
from app.models.models import Usuario
from app.schemas.internal_chat import (
    ChatInternoAutorOut,
    ChatInternoCanalOut,
    ChatInternoDiretoCreate,
    ChatInternoGrupoCreate,
    ChatInternoLeituraOut,
    ChatInternoMensagemCreate,
    ChatInternoMensagemOut,
    ChatInternoResumoOut,
)
from app.services.access_control import require_module_manage
from app.services.audit import add_audit_log
from app.services.db_utils import commit_or_conflict


router = APIRouter(prefix="/chat-interno", tags=["Chat interno"])


def _usuario_out(usuario: Usuario) -> ChatInternoAutorOut:
    return ChatInternoAutorOut(
        id=usuario.id,
        nome=usuario.nome,
        cargo=usuario.cargo,
        foto_perfil=usuario.foto_perfil,
        ativo=usuario.ativo,
    )


def _mensagem_out(
    mensagem: MensagemChatInterno,
    autor: Usuario,
) -> ChatInternoMensagemOut:
    return ChatInternoMensagemOut(
        id=mensagem.id,
        canal_id=mensagem.canal_id,
        conteudo=mensagem.conteudo,
        created_at=mensagem.created_at,
        autor=_usuario_out(autor),
    )


def _garantir_canal_geral(db: Session, empresa_id: int) -> CanalChatInterno:
    chave = f"GERAL:{empresa_id}"
    canal = db.scalar(
        select(CanalChatInterno).where(CanalChatInterno.chave_unica == chave)
    )
    if canal is not None:
        return canal

    db.execute(
        insert(CanalChatInterno)
        .values(
            empresa_id=empresa_id,
            tipo="GERAL",
            nome="Geral da empresa",
            chave_unica=chave,
        )
        .on_conflict_do_nothing(index_elements=["chave_unica"])
    )
    db.commit()

    canal = db.scalar(
        select(CanalChatInterno).where(CanalChatInterno.chave_unica == chave)
    )
    if canal is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Não foi possível preparar o chat geral da empresa.",
        )
    return canal


def _canais_disponiveis(
    db: Session,
    current_user: Usuario,
) -> list[CanalChatInterno]:
    _garantir_canal_geral(db, current_user.empresa_id)
    canais_membro = select(MembroCanalChatInterno.canal_id).where(
        MembroCanalChatInterno.usuario_id == current_user.id
    )
    return list(
        db.scalars(
            select(CanalChatInterno)
            .where(
                CanalChatInterno.empresa_id == current_user.empresa_id,
                or_(
                    CanalChatInterno.tipo == "GERAL",
                    CanalChatInterno.id.in_(canais_membro),
                ),
            )
            .order_by(CanalChatInterno.created_at)
        )
    )


def _obter_canal(
    db: Session,
    current_user: Usuario,
    canal_id: int,
) -> CanalChatInterno:
    canal = db.scalar(
        select(CanalChatInterno).where(
            CanalChatInterno.id == canal_id,
            CanalChatInterno.empresa_id == current_user.empresa_id,
        )
    )
    if canal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversa não encontrada.")

    if canal.tipo == "GERAL":
        return canal

    membro = db.scalar(
        select(MembroCanalChatInterno.id).where(
            MembroCanalChatInterno.canal_id == canal.id,
            MembroCanalChatInterno.usuario_id == current_user.id,
        )
    )
    if membro is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Você não participa desta conversa interna.",
        )
    return canal


def _membros_canal(
    db: Session,
    canal: CanalChatInterno,
) -> list[Usuario]:
    if canal.tipo == "GERAL":
        return list(
            db.scalars(
                select(Usuario)
                .where(
                    Usuario.empresa_id == canal.empresa_id,
                    Usuario.ativo.is_(True),
                )
                .order_by(Usuario.nome)
            )
        )

    return list(
        db.scalars(
            select(Usuario)
            .join(
                MembroCanalChatInterno,
                MembroCanalChatInterno.usuario_id == Usuario.id,
            )
            .where(MembroCanalChatInterno.canal_id == canal.id)
            .order_by(Usuario.nome)
        )
    )


def _ultima_mensagem_canal(
    db: Session,
    canal_id: int,
) -> tuple[MensagemChatInterno, Usuario] | None:
    return db.execute(
        select(MensagemChatInterno, Usuario)
        .join(Usuario, Usuario.id == MensagemChatInterno.usuario_id)
        .where(MensagemChatInterno.canal_id == canal_id)
        .order_by(MensagemChatInterno.id.desc())
        .limit(1)
    ).first()


def _nao_lidas_canal(
    db: Session,
    current_user: Usuario,
    canal_id: int,
) -> int:
    leitura = db.scalar(
        select(LeituraChatInterno).where(
            LeituraChatInterno.canal_id == canal_id,
            LeituraChatInterno.usuario_id == current_user.id,
        )
    )
    ultima_lida = leitura.ultima_mensagem_id if leitura else 0
    quantidade = db.scalar(
        select(func.count(MensagemChatInterno.id)).where(
            MensagemChatInterno.canal_id == canal_id,
            MensagemChatInterno.id > ultima_lida,
            MensagemChatInterno.usuario_id != current_user.id,
        )
    )
    return int(quantidade or 0)


def _nome_canal(
    canal: CanalChatInterno,
    membros: list[Usuario],
    current_user: Usuario,
) -> str:
    if canal.tipo == "GERAL":
        return "Geral da empresa"
    if canal.tipo == "GRUPO":
        return canal.nome or "Grupo sem nome"

    outro = next((item for item in membros if item.id != current_user.id), None)
    return outro.nome if outro else "Conversa direta"


def _canal_out(
    db: Session,
    canal: CanalChatInterno,
    current_user: Usuario,
) -> ChatInternoCanalOut:
    membros = _membros_canal(db, canal)
    ultima = _ultima_mensagem_canal(db, canal.id)
    ultima_out = _mensagem_out(*ultima) if ultima else None
    return ChatInternoCanalOut(
        id=canal.id,
        tipo=canal.tipo,
        nome=_nome_canal(canal, membros, current_user),
        created_at=canal.created_at,
        membros=[_usuario_out(item) for item in membros],
        ultima_mensagem=ultima_out,
        nao_lidas=_nao_lidas_canal(db, current_user, canal.id),
    )


@router.get("/usuarios", response_model=list[ChatInternoAutorOut])
def listar_usuarios_da_empresa(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatInternoAutorOut]:
    usuarios = db.scalars(
        select(Usuario)
        .where(
            Usuario.empresa_id == current_user.empresa_id,
            Usuario.ativo.is_(True),
            Usuario.id != current_user.id,
        )
        .order_by(Usuario.nome)
    )
    return [_usuario_out(item) for item in usuarios]


@router.get("/canais", response_model=list[ChatInternoCanalOut])
def listar_canais(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatInternoCanalOut]:
    canais = [
        _canal_out(db, canal, current_user)
        for canal in _canais_disponiveis(db, current_user)
    ]
    return sorted(
        canais,
        key=lambda item: (
            item.tipo == "GERAL",
            item.ultima_mensagem.created_at if item.ultima_mensagem else item.created_at,
        ),
        reverse=True,
    )


@router.post(
    "/diretos",
    response_model=ChatInternoCanalOut,
    status_code=status.HTTP_201_CREATED,
)
def criar_ou_obter_conversa_direta(
    data: ChatInternoDiretoCreate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatInternoCanalOut:
    if data.usuario_id == current_user.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Escolha outra pessoa para iniciar a conversa.",
        )

    destino = db.scalar(
        select(Usuario).where(
            Usuario.id == data.usuario_id,
            Usuario.empresa_id == current_user.empresa_id,
            Usuario.ativo.is_(True),
        )
    )
    if destino is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Usuário não encontrado na sua empresa.",
        )

    menor_id, maior_id = sorted((current_user.id, destino.id))
    chave = f"DIRETO:{current_user.empresa_id}:{menor_id}:{maior_id}"
    canal = db.scalar(
        select(CanalChatInterno).where(CanalChatInterno.chave_unica == chave)
    )

    if canal is None:
        canal = CanalChatInterno(
            empresa_id=current_user.empresa_id,
            tipo="DIRETO",
            criado_por_id=current_user.id,
            chave_unica=chave,
        )
        db.add(canal)
        db.flush()
        db.add_all(
            [
                MembroCanalChatInterno(
                    canal_id=canal.id,
                    usuario_id=current_user.id,
                ),
                MembroCanalChatInterno(
                    canal_id=canal.id,
                    usuario_id=destino.id,
                ),
            ]
        )
        commit_or_conflict(
            db,
            canal,
            "Essa conversa foi criada por outra ação. Atualize e tente novamente.",
        )

    return _canal_out(db, canal, current_user)


@router.post(
    "/grupos",
    response_model=ChatInternoCanalOut,
    status_code=status.HTTP_201_CREATED,
)
def criar_grupo(
    data: ChatInternoGrupoCreate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatInternoCanalOut:
    require_module_manage(db, current_user, "CHAT_INTERNO")
    nome = data.nome.strip()
    ids = {item for item in data.usuario_ids if item != current_user.id}
    if not nome:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Digite o nome do grupo.")
    if not ids:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Escolha pelo menos uma pessoa para o grupo.",
        )

    usuarios = list(
        db.scalars(
            select(Usuario).where(
                Usuario.id.in_(ids),
                Usuario.empresa_id == current_user.empresa_id,
                Usuario.ativo.is_(True),
            )
        )
    )
    if len(usuarios) != len(ids):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Um ou mais participantes não pertencem à sua empresa.",
        )

    canal = CanalChatInterno(
        empresa_id=current_user.empresa_id,
        tipo="GRUPO",
        nome=nome,
        criado_por_id=current_user.id,
    )
    db.add(canal)
    db.flush()
    membros_ids = [current_user.id, *sorted(ids)]
    db.add_all(
        [
            MembroCanalChatInterno(canal_id=canal.id, usuario_id=usuario_id)
            for usuario_id in membros_ids
        ]
    )
    add_audit_log(
        db,
        user=current_user,
        action="CRIOU_GRUPO_CHAT_INTERNO",
        entity="canais_chat_interno",
        entity_id=canal.id,
        details={"nome": nome, "participantes": len(membros_ids)},
    )
    commit_or_conflict(db, canal)
    return _canal_out(db, canal, current_user)


@router.delete("/grupos/{canal_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_grupo(
    canal_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_module_manage(db, current_user, "CHAT_INTERNO")
    canal = _obter_canal(db, current_user, canal_id)
    if canal.tipo != "GRUPO":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Somente grupos criados pela equipe podem ser excluídos.",
        )

    nome = canal.nome or f"Grupo #{canal.id}"
    entity_id = canal.id
    db.delete(canal)
    add_audit_log(
        db,
        user=current_user,
        action="EXCLUIU_GRUPO_CHAT_INTERNO",
        entity="canais_chat_interno",
        entity_id=entity_id,
        details={"nome": nome},
    )
    commit_or_conflict(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/resumo", response_model=ChatInternoResumoOut)
def obter_resumo(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatInternoResumoOut:
    canais_membro = select(MembroCanalChatInterno.canal_id).where(
        MembroCanalChatInterno.usuario_id == current_user.id
    )
    canais_disponiveis = (
        select(CanalChatInterno.id)
        .where(
            CanalChatInterno.empresa_id == current_user.empresa_id,
            or_(
                CanalChatInterno.tipo == "GERAL",
                CanalChatInterno.id.in_(canais_membro),
            ),
        )
        .subquery()
    )

    row = db.execute(
        select(
            func.max(MensagemChatInterno.id).label("ultima_mensagem_id"),
            func.count(MensagemChatInterno.id)
            .filter(
                MensagemChatInterno.usuario_id != current_user.id,
                MensagemChatInterno.id
                > func.coalesce(LeituraChatInterno.ultima_mensagem_id, 0),
            )
            .label("nao_lidas"),
        )
        .select_from(MensagemChatInterno)
        .join(
            canais_disponiveis,
            canais_disponiveis.c.id == MensagemChatInterno.canal_id,
        )
        .outerjoin(
            LeituraChatInterno,
            (LeituraChatInterno.canal_id == MensagemChatInterno.canal_id)
            & (LeituraChatInterno.usuario_id == current_user.id),
        )
    ).one()

    return ChatInternoResumoOut(
        nao_lidas=int(row.nao_lidas or 0),
        ultima_mensagem_id=row.ultima_mensagem_id,
    )


@router.post(
    "/canais/{canal_id}/marcar-lido",
    response_model=ChatInternoLeituraOut,
)
def marcar_como_lido(
    canal_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatInternoLeituraOut:
    _obter_canal(db, current_user, canal_id)
    ultima_mensagem_id = db.scalar(
        select(func.max(MensagemChatInterno.id)).where(
            MensagemChatInterno.canal_id == canal_id
        )
    ) or 0
    leitura = db.scalar(
        select(LeituraChatInterno).where(
            LeituraChatInterno.canal_id == canal_id,
            LeituraChatInterno.usuario_id == current_user.id,
        )
    )

    agora = datetime.now(timezone.utc)
    if leitura is None:
        leitura = LeituraChatInterno(
            canal_id=canal_id,
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
        canal_id=canal_id,
        ultima_mensagem_id=leitura.ultima_mensagem_id,
        updated_at=leitura.updated_at,
    )


@router.get(
    "/canais/{canal_id}/mensagens",
    response_model=list[ChatInternoMensagemOut],
)
def listar_mensagens(
    canal_id: int,
    antes_de_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=120, ge=1, le=300),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatInternoMensagemOut]:
    _obter_canal(db, current_user, canal_id)
    query = (
        select(MensagemChatInterno, Usuario)
        .join(Usuario, Usuario.id == MensagemChatInterno.usuario_id)
        .where(
            MensagemChatInterno.canal_id == canal_id,
            MensagemChatInterno.empresa_id == current_user.empresa_id,
        )
    )
    if antes_de_id is not None:
        query = query.where(MensagemChatInterno.id < antes_de_id)

    rows = db.execute(
        query.order_by(MensagemChatInterno.id.desc()).limit(limit)
    ).all()
    return [_mensagem_out(mensagem, autor) for mensagem, autor in reversed(rows)]


@router.post(
    "/canais/{canal_id}/mensagens",
    response_model=ChatInternoMensagemOut,
    status_code=status.HTTP_201_CREATED,
)
def enviar_mensagem(
    canal_id: int,
    data: ChatInternoMensagemCreate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatInternoMensagemOut:
    _obter_canal(db, current_user, canal_id)
    conteudo = data.conteudo.strip()
    if not conteudo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Digite uma mensagem antes de enviar.",
        )

    mensagem = MensagemChatInterno(
        canal_id=canal_id,
        empresa_id=current_user.empresa_id,
        usuario_id=current_user.id,
        conteudo=conteudo,
    )
    db.add(mensagem)
    commit_or_conflict(db, mensagem)
    return _mensagem_out(mensagem, current_user)
