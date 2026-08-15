from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.models.enums import RemetenteMensagem, StatusCliente
from app.models.models import (
    Agendamento,
    Cliente,
    Conversa,
    Empresa,
    Integracao,
    Mensagem,
    Plano,
    Usuario,
)
from app.models.platform import EmpresaPlataforma, PlanoConfiguracao


RECURSOS_PADRAO: dict[str, bool] = {
    "AGENDA": True,
    "CLIENTES": True,
    "VEICULOS": True,
    "SERVICOS": True,
    "CONVERSAS": True,
    "NOTIFICACOES": True,
    "WHATSAPP": False,
    "INSTAGRAM": False,
    "INTELIGENCIA_ARTIFICIAL": False,
    "AVALIACOES": False,
    "RELATORIOS": False,
    "AUTOMACOES": False,
    "MULTIPLAS_UNIDADES": False,
    "SUPORTE_PRIORITARIO": False,
}

LIMIT_KEYS = {
    "usuarios": "limite_usuarios",
    "clientes": "limite_clientes",
    "agendamentos_mes": "limite_agendamentos_mes",
    "conversas_mes": "limite_conversas_mes",
    "mensagens_ia_mes": "limite_mensagens_ia_mes",
    "canais": "limite_canais",
    "armazenamento_mb": "limite_armazenamento_mb",
}


@dataclass
class PlanoEfetivo:
    empresa: Empresa
    plano: Plano | None
    configuracao: PlanoConfiguracao | None
    plataforma: EmpresaPlataforma | None
    recursos: dict[str, bool]
    limites: dict[str, int | None]


def _month_bounds(reference: date | None = None) -> tuple[datetime, datetime]:
    target = reference or datetime.now(timezone.utc).date()
    start = datetime.combine(target.replace(day=1), time.min, tzinfo=timezone.utc)
    last_day = monthrange(target.year, target.month)[1]
    end = datetime.combine(
        target.replace(day=last_day), time.max, tzinfo=timezone.utc
    )
    return start, end


def _fallback_policy(empresa: Empresa) -> PlanoEfetivo:
    return PlanoEfetivo(
        empresa=empresa,
        plano=None,
        configuracao=None,
        plataforma=None,
        recursos={**RECURSOS_PADRAO, "WHATSAPP": True, "INSTAGRAM": True},
        limites={key: None for key in LIMIT_KEYS},
    )


def get_effective_plan(db: Session, empresa_id: int) -> PlanoEfetivo:
    """Carrega empresa, plano, configuração e overrides em um único round trip."""
    try:
        row = db.execute(
            select(Empresa, Plano, PlanoConfiguracao, EmpresaPlataforma)
            .outerjoin(Plano, Plano.id == Empresa.plano_id)
            .outerjoin(
                PlanoConfiguracao,
                PlanoConfiguracao.plano_id == Empresa.plano_id,
            )
            .outerjoin(
                EmpresaPlataforma,
                EmpresaPlataforma.empresa_id == Empresa.id,
            )
            .where(Empresa.id == empresa_id)
        ).one_or_none()
    except ProgrammingError:
        db.rollback()
        empresa = db.get(Empresa, empresa_id)
        if empresa is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa não encontrada.")
        return _fallback_policy(empresa)

    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa não encontrada.")

    empresa, plano, configuracao, plataforma = row

    recursos = dict(RECURSOS_PADRAO)
    if configuracao and configuracao.recursos:
        recursos.update(
            {key: bool(value) for key, value in configuracao.recursos.items()}
        )
    if plataforma and plataforma.recursos_personalizados:
        recursos.update(
            {
                key: bool(value)
                for key, value in plataforma.recursos_personalizados.items()
            }
        )

    ia_ativa = bool(
        configuracao
        and (
            configuracao.ia_incluida
            or (
                configuracao.ia_adicional_disponivel
                and plataforma
                and plataforma.ia_adicional_ativo
            )
        )
    )
    recursos["INTELIGENCIA_ARTIFICIAL"] = ia_ativa

    limites: dict[str, int | None] = {}
    for public_key, model_key in LIMIT_KEYS.items():
        value = getattr(configuracao, model_key, None) if configuracao else None
        if plataforma and public_key in plataforma.limites_personalizados:
            value = plataforma.limites_personalizados[public_key]
        limites[public_key] = int(value) if value is not None else None

    if ia_ativa and plataforma:
        base = limites["mensagens_ia_mes"] or 0
        limites["mensagens_ia_mes"] = base + plataforma.ia_limite_adicional

    return PlanoEfetivo(
        empresa=empresa,
        plano=plano,
        configuracao=configuracao,
        plataforma=plataforma,
        recursos=recursos,
        limites=limites,
    )


def get_company_usage(db: Session, empresa_id: int) -> dict[str, int]:
    """Calcula todos os contadores de consumo em uma única consulta SQL."""
    month_start, month_end = _month_bounds()

    usuarios = (
        select(func.count(Usuario.id))
        .where(
            Usuario.empresa_id == empresa_id,
            Usuario.ativo.is_(True),
        )
        .scalar_subquery()
    )
    clientes = (
        select(func.count(Cliente.id))
        .where(
            Cliente.empresa_id == empresa_id,
            Cliente.status != StatusCliente.INATIVO,
        )
        .scalar_subquery()
    )
    agendamentos = (
        select(func.count(Agendamento.id))
        .where(
            Agendamento.empresa_id == empresa_id,
            Agendamento.created_at >= month_start,
            Agendamento.created_at <= month_end,
        )
        .scalar_subquery()
    )
    conversas = (
        select(func.count(Conversa.id))
        .where(
            Conversa.empresa_id == empresa_id,
            Conversa.created_at >= month_start,
            Conversa.created_at <= month_end,
        )
        .scalar_subquery()
    )
    canais = (
        select(func.count(Integracao.id))
        .where(
            Integracao.empresa_id == empresa_id,
            Integracao.ativo.is_(True),
        )
        .scalar_subquery()
    )
    mensagens_ia = (
        select(func.count(Mensagem.id))
        .join(Conversa, Conversa.id == Mensagem.conversa_id)
        .where(
            Conversa.empresa_id == empresa_id,
            Mensagem.remetente == RemetenteMensagem.IA,
            Mensagem.data_envio >= month_start,
            Mensagem.data_envio <= month_end,
        )
        .scalar_subquery()
    )

    row = db.execute(
        select(
            usuarios.label("usuarios"),
            clientes.label("clientes"),
            agendamentos.label("agendamentos_mes"),
            conversas.label("conversas_mes"),
            canais.label("canais"),
            mensagens_ia.label("mensagens_ia_mes"),
        )
    ).one()

    return {
        "usuarios": int(row.usuarios or 0),
        "clientes": int(row.clientes or 0),
        "agendamentos_mes": int(row.agendamentos_mes or 0),
        "conversas_mes": int(row.conversas_mes or 0),
        "canais": int(row.canais or 0),
        "mensagens_ia_mes": int(row.mensagens_ia_mes or 0),
        "armazenamento_mb": 0,
    }


def require_feature(db: Session, empresa_id: int, feature: str) -> None:
    policy = get_effective_plan(db, empresa_id)
    if not policy.recursos.get(feature, False):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"O recurso {feature.replace('_', ' ').title()} não está liberado no plano atual.",
        )


def enforce_limit(db: Session, empresa_id: int, limit_key: str) -> None:
    if limit_key not in LIMIT_KEYS:
        raise ValueError(f"Limite desconhecido: {limit_key}")

    policy = get_effective_plan(db, empresa_id)
    limit = policy.limites.get(limit_key)
    if limit is None:
        return

    usage = get_company_usage(db, empresa_id).get(limit_key, 0)
    if usage >= limit:
        labels = {
            "usuarios": "usuários ativos",
            "clientes": "clientes",
            "agendamentos_mes": "agendamentos mensais",
            "conversas_mes": "conversas mensais",
            "mensagens_ia_mes": "mensagens mensais de IA",
            "canais": "canais conectados",
            "armazenamento_mb": "armazenamento",
        }
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            (
                f"O limite de {labels[limit_key]} do plano foi atingido "
                f"({usage} de {limit})."
            ),
        )


def plan_snapshot(policy: PlanoEfetivo) -> dict[str, Any]:
    return {
        "plano_id": policy.plano.id if policy.plano else None,
        "plano_nome": policy.plano.nome if policy.plano else None,
        "recursos": policy.recursos,
        "limites": policy.limites,
    }
