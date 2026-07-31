from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.database import get_db
from app.models.enums import CargoUsuario
from app.models.models import Assinatura, Usuario
from app.schemas.reports import PlanoConsumoItem, PlanoEmpresaOut
from app.services.plans import get_company_usage, get_effective_plan


router = APIRouter(prefix="/plano-atual", tags=["Plano e consumo"])


NOMES_CONSUMO = {
    "usuarios": "Usuários ativos",
    "clientes": "Clientes",
    "agendamentos_mes": "Agendamentos no mês",
    "conversas_mes": "Conversas no mês",
    "mensagens_ia_mes": "Mensagens de IA no mês",
    "canais": "Canais conectados",
    "armazenamento_mb": "Armazenamento em MB",
}


@router.get("", response_model=PlanoEmpresaOut)
def plano_atual(
    current_user: Usuario = Depends(require_roles(CargoUsuario.ADMIN)),
    db: Session = Depends(get_db),
) -> PlanoEmpresaOut:
    policy = get_effective_plan(db, current_user.empresa_id)
    usage = get_company_usage(db, current_user.empresa_id)
    assinatura = db.scalar(
        select(Assinatura)
        .where(Assinatura.empresa_id == current_user.empresa_id)
        .order_by(Assinatura.created_at.desc())
        .limit(1)
    )

    consumo = [
        PlanoConsumoItem(
            chave=chave,
            nome=NOMES_CONSUMO[chave],
            utilizado=int(usage.get(chave, 0)),
            limite=policy.limites.get(chave),
        )
        for chave in NOMES_CONSUMO
    ]

    plataforma = policy.plataforma
    configuracao = policy.configuracao
    return PlanoEmpresaOut(
        plano_id=policy.plano.id if policy.plano else None,
        plano_nome=policy.plano.nome if policy.plano else None,
        descricao=policy.plano.descricao if policy.plano else None,
        preco_mensal=policy.plano.preco if policy.plano else None,
        preco_anual=configuracao.preco_anual if configuracao else None,
        status_empresa=plataforma.status if plataforma else None,
        status_assinatura=assinatura.status.value if assinatura else None,
        trial_fim=plataforma.trial_fim if plataforma else None,
        data_inicio=assinatura.data_inicio if assinatura else None,
        data_vencimento=assinatura.data_vencimento if assinatura else None,
        ia_ativa=policy.recursos.get("INTELIGENCIA_ARTIFICIAL", False),
        ia_adicional_ativo=(
            bool(plataforma.ia_adicional_ativo) if plataforma else False
        ),
        recursos=policy.recursos,
        consumo=consumo,
    )
