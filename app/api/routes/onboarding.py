from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.database import get_db
from app.models.engagement import EmpresaOnboarding
from app.models.enums import CargoUsuario, TipoIntegracao
from app.models.models import Agendamento, Cliente, ConfigIA, Empresa, Horario, Integracao, Servico, Usuario
from app.schemas.engagement import OnboardingEtapaOut, OnboardingOcultarInput, OnboardingOut

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


def _estado(db: Session, empresa_id: int) -> EmpresaOnboarding:
    estado = db.scalar(select(EmpresaOnboarding).where(EmpresaOnboarding.empresa_id == empresa_id))
    if estado is None:
        estado = EmpresaOnboarding(empresa_id=empresa_id, oculto=False)
        db.add(estado)
        db.flush()
    return estado


def _quantidade(db: Session, model: type, empresa_id: int, *filtros: object) -> int:
    return int(db.scalar(select(func.count(model.id)).where(model.empresa_id == empresa_id, *filtros)) or 0)


def _resultado(db: Session, empresa_id: int) -> OnboardingOut:
    empresa = db.get(Empresa, empresa_id)
    estado = _estado(db, empresa_id)
    dados_empresa = bool(
        empresa and empresa.nome and empresa.cnpj and empresa.telefone
        and empresa.email and empresa.cidade and empresa.estado
    )
    servicos = _quantidade(db, Servico, empresa_id, Servico.ativo.is_(True))
    usuarios = _quantidade(db, Usuario, empresa_id, Usuario.ativo.is_(True))
    horarios = _quantidade(db, Horario, empresa_id, Horario.ativo.is_(True))
    clientes = _quantidade(db, Cliente, empresa_id)
    agendamentos = _quantidade(db, Agendamento, empresa_id)
    whatsapp = _quantidade(
        db,
        Integracao,
        empresa_id,
        Integracao.ativo.is_(True),
        Integracao.tipo == TipoIntegracao.WHATSAPP,
    )
    config_ia = db.scalar(select(ConfigIA.id).where(ConfigIA.empresa_id == empresa_id))

    etapas = [
        OnboardingEtapaOut(chave="empresa", titulo="Complete os dados da empresa", descricao="Informe telefone, e-mail, cidade e estado.", concluida=dados_empresa, link="/configuracoes"),
        OnboardingEtapaOut(chave="servico", titulo="Cadastre o primeiro serviço", descricao="Defina preço, duração e adicionais do atendimento.", concluida=servicos > 0, link="/servicos?novo=1"),
        OnboardingEtapaOut(chave="equipe", titulo="Cadastre a equipe", descricao="Adicione pelo menos um usuário além do administrador.", concluida=usuarios > 1, link="/equipe"),
        OnboardingEtapaOut(chave="jornada", titulo="Configure as jornadas", descricao="Informe os dias e horários disponíveis da equipe.", concluida=horarios > 0, link="/equipe"),
        OnboardingEtapaOut(chave="cliente", titulo="Cadastre o primeiro cliente", descricao="Crie a base inicial de relacionamento da empresa.", concluida=clientes > 0, link="/clientes?novo=1"),
        OnboardingEtapaOut(chave="agendamento", titulo="Crie o primeiro agendamento", descricao="Teste o fluxo completo da agenda.", concluida=agendamentos > 0, link="/agenda?novo=1"),
        OnboardingEtapaOut(chave="whatsapp", titulo="Conecte o WhatsApp", descricao="Prepare o canal principal de atendimento.", concluida=whatsapp > 0, link="/configuracoes"),
        OnboardingEtapaOut(chave="ia", titulo="Configure a inteligência artificial", descricao="Defina a identidade e as orientações do assistente.", concluida=config_ia is not None, link="/configuracoes"),
    ]
    concluidas = sum(1 for item in etapas if item.concluida)
    concluido = concluidas == len(etapas)
    if concluido and estado.concluido_em is None:
        estado.concluido_em = datetime.now(timezone.utc)
        estado.updated_at = datetime.now(timezone.utc)
        db.flush()
    return OnboardingOut(
        oculto=estado.oculto,
        concluido=concluido,
        percentual=round((concluidas / len(etapas)) * 100),
        concluidas=concluidas,
        total=len(etapas),
        etapas=etapas,
    )


@router.get("", response_model=OnboardingOut)
def obter_onboarding(
    current_user: Usuario = Depends(require_roles(CargoUsuario.ADMIN)),
    db: Session = Depends(get_db),
) -> OnboardingOut:
    resultado = _resultado(db, current_user.empresa_id)
    db.commit()
    return resultado


@router.patch("/visibilidade", response_model=OnboardingOut)
def alterar_visibilidade(
    data: OnboardingOcultarInput,
    current_user: Usuario = Depends(require_roles(CargoUsuario.ADMIN)),
    db: Session = Depends(get_db),
) -> OnboardingOut:
    estado = _estado(db, current_user.empresa_id)
    estado.oculto = data.oculto
    estado.updated_at = datetime.now(timezone.utc)
    db.commit()
    return _resultado(db, current_user.empresa_id)
