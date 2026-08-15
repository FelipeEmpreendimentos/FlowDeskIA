from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.chat_interno import _garantir_canal_geral
from app.database.database import get_db
from app.models.models import Usuario
from app.schemas.internal_chat import ChatInternoCanalOut


router = APIRouter(prefix="/chat-interno", tags=["Chat interno"])


CANAIS_SQL = text(
    """
    SELECT
        c.id,
        c.tipo,
        CASE
            WHEN c.tipo = 'GERAL' THEN 'Geral da empresa'
            WHEN c.tipo = 'GRUPO' THEN COALESCE(c.nome, 'Grupo sem nome')
            ELSE COALESCE((
                SELECT u.nome
                FROM membros_canais_chat_interno mc_nome
                JOIN usuarios u ON u.id = mc_nome.usuario_id
                WHERE mc_nome.canal_id = c.id
                  AND u.id <> :usuario_id
                ORDER BY u.id
                LIMIT 1
            ), 'Conversa direta')
        END AS nome,
        c.created_at,
        COALESCE(
            CASE
                WHEN c.tipo = 'GERAL' THEN (
                    SELECT jsonb_agg(
                        jsonb_build_object(
                            'id', u.id,
                            'nome', u.nome,
                            'cargo', u.cargo,
                            'foto_perfil', u.foto_perfil,
                            'ativo', u.ativo
                        )
                        ORDER BY u.nome
                    )
                    FROM usuarios u
                    WHERE u.empresa_id = :empresa_id
                      AND u.ativo = TRUE
                )
                ELSE (
                    SELECT jsonb_agg(
                        jsonb_build_object(
                            'id', u.id,
                            'nome', u.nome,
                            'cargo', u.cargo,
                            'foto_perfil', u.foto_perfil,
                            'ativo', u.ativo
                        )
                        ORDER BY u.nome
                    )
                    FROM membros_canais_chat_interno mc
                    JOIN usuarios u ON u.id = mc.usuario_id
                    WHERE mc.canal_id = c.id
                )
            END,
            '[]'::jsonb
        ) AS membros,
        (
            SELECT jsonb_build_object(
                'id', m.id,
                'canal_id', m.canal_id,
                'conteudo', m.conteudo,
                'created_at', m.created_at,
                'autor', jsonb_build_object(
                    'id', autor.id,
                    'nome', autor.nome,
                    'cargo', autor.cargo,
                    'foto_perfil', autor.foto_perfil,
                    'ativo', autor.ativo
                )
            )
            FROM mensagens_canais_chat_interno m
            JOIN usuarios autor ON autor.id = m.usuario_id
            WHERE m.canal_id = c.id
            ORDER BY m.id DESC
            LIMIT 1
        ) AS ultima_mensagem,
        (
            SELECT COUNT(*)
            FROM mensagens_canais_chat_interno m_nao_lida
            WHERE m_nao_lida.canal_id = c.id
              AND m_nao_lida.usuario_id <> :usuario_id
              AND m_nao_lida.id > COALESCE((
                  SELECT leitura.ultima_mensagem_id
                  FROM leituras_canais_chat_interno leitura
                  WHERE leitura.canal_id = c.id
                    AND leitura.usuario_id = :usuario_id
                  LIMIT 1
              ), 0)
        ) AS nao_lidas,
        COALESCE((
            SELECT MAX(m_ordem.created_at)
            FROM mensagens_canais_chat_interno m_ordem
            WHERE m_ordem.canal_id = c.id
        ), c.created_at) AS ultima_atividade
    FROM canais_chat_interno c
    WHERE c.empresa_id = :empresa_id
      AND (
          c.tipo = 'GERAL'
          OR EXISTS (
              SELECT 1
              FROM membros_canais_chat_interno mc_acesso
              WHERE mc_acesso.canal_id = c.id
                AND mc_acesso.usuario_id = :usuario_id
          )
      )
    ORDER BY
        (c.tipo = 'GERAL') DESC,
        ultima_atividade DESC
    """
)


def _listar_canais_agregados(
    db: Session,
    *,
    empresa_id: int,
    usuario_id: int,
) -> list[ChatInternoCanalOut]:
    rows = db.execute(
        CANAIS_SQL,
        {"empresa_id": empresa_id, "usuario_id": usuario_id},
    ).mappings().all()

    return [
        ChatInternoCanalOut.model_validate(
            {
                "id": row["id"],
                "tipo": row["tipo"],
                "nome": row["nome"],
                "created_at": row["created_at"],
                "membros": row["membros"] or [],
                "ultima_mensagem": row["ultima_mensagem"],
                "nao_lidas": int(row["nao_lidas"] or 0),
            }
        )
        for row in rows
    ]


@router.get("/canais", response_model=list[ChatInternoCanalOut])
def listar_canais_otimizado(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatInternoCanalOut]:
    canais = _listar_canais_agregados(
        db,
        empresa_id=current_user.empresa_id,
        usuario_id=current_user.id,
    )

    # Bancos novos recebem o canal Geral no setup. O fallback mantém a mesma
    # garantia para empresas criadas em uma instalação antiga, sem acrescentar
    # consultas no caminho normal.
    if not any(item.tipo == "GERAL" for item in canais):
        _garantir_canal_geral(db, current_user.empresa_id)
        canais = _listar_canais_agregados(
            db,
            empresa_id=current_user.empresa_id,
            usuario_id=current_user.id,
        )

    return canais
