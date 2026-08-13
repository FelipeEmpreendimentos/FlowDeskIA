from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.database import get_db
from app.models.enums import CargoUsuario
from app.models.models import Log, Usuario
from app.schemas.reports import AtividadeOut


router = APIRouter(prefix="/atividades", tags=["Atividades"])


ACOES = {
    "CRIOU_AGENDAMENTO": "criou um agendamento",
    "ATUALIZOU_AGENDAMENTO": "atualizou um agendamento",
    "CANCELOU_AGENDAMENTO": "cancelou um agendamento",
    "FECHOU_ATENDIMENTO": "fechou financeiramente um atendimento",
    "REGISTROU_PAGAMENTO": "registrou um pagamento",
    "AJUSTOU_FECHAMENTO": "ajustou um fechamento financeiro",
    "ESTORNOU_PAGAMENTO": "estornou um pagamento",
    "CRIOU_CLIENTE": "cadastrou um cliente",
    "ATUALIZOU_CLIENTE": "atualizou um cliente",
    "DESATIVOU_CLIENTE": "desativou um cliente",
    "CRIOU_VEICULO": "cadastrou um veículo",
    "ATUALIZOU_VEICULO": "atualizou um veículo",
    "EXCLUIU_VEICULO": "excluiu um veículo",
    "CRIOU_SERVICO": "cadastrou um serviço",
    "ATUALIZOU_SERVICO": "atualizou um serviço",
    "DESATIVOU_SERVICO": "desativou um serviço",
    "CRIOU_USUARIO": "cadastrou um usuário",
    "ATUALIZOU_USUARIO": "atualizou um usuário",
    "DESATIVOU_USUARIO": "desativou um usuário",
}

AREAS = {
    "agendamentos": "agendamentos agenda atendimento",
    "fechamentos_financeiros": "financeiro fechamento",
    "pagamentos_atendimento": "pagamentos recebimentos",
    "clientes": "clientes",
    "veiculos": "veículos veiculos carros",
    "servicos": "serviços servicos",
    "usuarios": "equipe usuários usuarios funcionários funcionarios",
    "conversas": "conversas atendimento mensagens",
}


def _descricao(log: Log, usuario: Usuario | None) -> str:
    ator = usuario.nome if usuario else "Sistema"
    acao = ACOES.get(log.acao, log.acao.lower().replace("_", " "))
    complemento = ""
    if log.entidade_id is not None:
        complemento = f" #{log.entidade_id}"
    return f"{ator} {acao}{complemento}."


@router.get("", response_model=list[AtividadeOut])
def listar_atividades(
    data_inicio: date | None = None,
    data_fim: date | None = None,
    usuario_id: int | None = None,
    entidade: str | None = None,
    busca: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=300),
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> list[AtividadeOut]:
    query = (
        select(Log, Usuario)
        .outerjoin(Usuario, Usuario.id == Log.ator_id)
        .where(Log.empresa_id == current_user.empresa_id)
    )

    if data_inicio:
        query = query.where(
            Log.created_at
            >= datetime.combine(data_inicio, time.min, tzinfo=timezone.utc)
        )
    if data_fim:
        query = query.where(
            Log.created_at
            <= datetime.combine(data_fim, time.max, tzinfo=timezone.utc)
        )
    if usuario_id:
        query = query.where(Log.ator_id == usuario_id)
    if entidade:
        query = query.where(Log.entidade == entidade)
    if busca and busca.strip():
        texto = busca.strip()
        termo = f"%{texto}%"
        normalizado = texto.casefold()
        condicoes = [
            Log.acao.ilike(termo),
            Log.entidade.ilike(termo),
            Usuario.nome.ilike(termo),
        ]

        acoes_correspondentes = [
            codigo
            for codigo, descricao in ACOES.items()
            if normalizado in descricao.casefold()
            or normalizado in codigo.replace("_", " ").casefold()
        ]
        if acoes_correspondentes:
            condicoes.append(Log.acao.in_(acoes_correspondentes))

        areas_correspondentes = [
            codigo
            for codigo, termos in AREAS.items()
            if normalizado in termos.casefold()
        ]
        if areas_correspondentes:
            condicoes.append(Log.entidade.in_(areas_correspondentes))

        identificador = texto.removeprefix("#")
        if identificador.isdigit():
            condicoes.append(Log.entidade_id == int(identificador))

        query = query.where(or_(*condicoes))

    rows = db.execute(
        query.order_by(Log.created_at.desc()).offset(offset).limit(limit)
    ).all()
    return [
        AtividadeOut(
            id=log.id,
            usuario_id=log.ator_id,
            usuario_nome=usuario.nome if usuario else None,
            usuario_cargo=usuario.cargo.value if usuario else None,
            acao=log.acao,
            entidade=log.entidade,
            entidade_id=log.entidade_id,
            descricao=_descricao(log, usuario),
            detalhes=log.detalhes,
            created_at=log.created_at,
        )
        for log, usuario in rows
    ]
