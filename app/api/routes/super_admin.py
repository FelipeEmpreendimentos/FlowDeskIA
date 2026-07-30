from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.super_admin_deps import get_current_super_admin
from app.core.security import (
    create_super_admin_access_token,
    hash_password,
    verify_password,
)
from app.database.database import get_db
from app.models.enums import CargoUsuario, StatusAssinatura
from app.models.models import (
    Agendamento,
    Assinatura,
    ConfigIA,
    Conversa,
    Empresa,
    Plano,
    Usuario,
)
from app.models.platform import (
    EmpresaPlataforma,
    PlanoConfiguracao,
    SuperAdmin,
    SuperAdminLog,
)
from app.schemas.common import MessageResponse
from app.schemas.super_admin import (
    ConfigIASuperAdminOut,
    ConfigIASuperAdminUpdate,
    DashboardSuperAdminOut,
    EmpresaDetalheOut,
    EmpresaResumoOut,
    EmpresaSuperAdminCreate,
    EmpresaSuperAdminUpdate,
    PlanoCreate,
    PlanoOut,
    PlanoUpdate,
    SuperAdminAlterarSenhaRequest,
    SuperAdminLoginRequest,
    SuperAdminLogOut,
    SuperAdminOut,
    SuperAdminTokenResponse,
)
from app.services.plans import get_company_usage, get_effective_plan

router = APIRouter(prefix="/super-admin", tags=["Super Admin"])

PLAN_FIELDS = {"nome", "descricao", "preco", "ativo"}
CONFIG_FIELDS = {
    "preco_anual",
    "periodo_teste_dias",
    "limite_usuarios",
    "limite_clientes",
    "limite_agendamentos_mes",
    "limite_conversas_mes",
    "limite_mensagens_ia_mes",
    "limite_canais",
    "limite_armazenamento_mb",
    "ia_incluida",
    "ia_adicional_disponivel",
    "recursos",
}


def _ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _log(
    db: Session,
    *,
    super_admin: SuperAdmin,
    request: Request,
    acao: str,
    entidade: str | None = None,
    entidade_id: int | None = None,
    empresa_id: int | None = None,
    anteriores: dict | None = None,
    novos: dict | None = None,
) -> None:
    db.add(
        SuperAdminLog(
            super_admin_id=super_admin.id,
            empresa_id=empresa_id,
            acao=acao,
            entidade=entidade,
            entidade_id=entidade_id,
            dados_anteriores=anteriores,
            dados_novos=novos,
            ip=_ip(request),
        )
    )


def _get_plan(db: Session, plan_id: int) -> tuple[Plano, PlanoConfiguracao]:
    plan = db.get(Plano, plan_id)
    config = db.get(PlanoConfiguracao, plan_id)
    if plan is None or config is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plano não encontrado.")
    return plan, config


def _plan_out(plan: Plano, config: PlanoConfiguracao) -> PlanoOut:
    return PlanoOut(
        id=plan.id,
        codigo=config.codigo,
        nome=plan.nome,
        descricao=plan.descricao,
        preco=plan.preco,
        preco_anual=config.preco_anual,
        ativo=plan.ativo,
        periodo_teste_dias=config.periodo_teste_dias,
        limite_usuarios=config.limite_usuarios,
        limite_clientes=config.limite_clientes,
        limite_agendamentos_mes=config.limite_agendamentos_mes,
        limite_conversas_mes=config.limite_conversas_mes,
        limite_mensagens_ia_mes=config.limite_mensagens_ia_mes,
        limite_canais=config.limite_canais,
        limite_armazenamento_mb=config.limite_armazenamento_mb,
        ia_incluida=config.ia_incluida,
        ia_adicional_disponivel=config.ia_adicional_disponivel,
        recursos=config.recursos or {},
        created_at=plan.created_at,
        updated_at=config.updated_at,
    )


def _get_platform(db: Session, empresa: Empresa) -> EmpresaPlataforma:
    platform = db.get(EmpresaPlataforma, empresa.id)
    if platform is None:
        platform = EmpresaPlataforma(
            empresa_id=empresa.id,
            status="ATIVA" if empresa.ativo else "SUSPENSA",
            recursos_personalizados={},
            limites_personalizados={},
        )
        db.add(platform)
        db.flush()
    return platform


def _current_subscription(db: Session, empresa_id: int) -> Assinatura | None:
    return db.scalar(
        select(Assinatura)
        .where(Assinatura.empresa_id == empresa_id)
        .order_by(Assinatura.created_at.desc())
        .limit(1)
    )


def _company_summary(db: Session, empresa: Empresa) -> EmpresaResumoOut:
    platform = _get_platform(db, empresa)
    usage = get_company_usage(db, empresa.id)
    plan = db.get(Plano, empresa.plano_id) if empresa.plano_id else None
    return EmpresaResumoOut(
        id=empresa.id,
        nome=empresa.nome,
        cnpj=empresa.cnpj,
        email=empresa.email,
        cidade=empresa.cidade,
        estado=empresa.estado,
        ativo=empresa.ativo,
        status=platform.status,
        plano_id=empresa.plano_id,
        plano_nome=plan.nome if plan else None,
        trial_fim=platform.trial_fim,
        usuarios_ativos=usage["usuarios"],
        clientes=usage["clientes"],
        agendamentos_mes=usage["agendamentos_mes"],
        conversas_mes=usage["conversas_mes"],
        ia_adicional_ativo=platform.ia_adicional_ativo,
        created_at=empresa.created_at,
    )


@router.post("/auth/login", response_model=SuperAdminTokenResponse)
def login_super_admin(
    data: SuperAdminLoginRequest,
    db: Session = Depends(get_db),
) -> SuperAdminTokenResponse:
    item = db.scalar(
        select(SuperAdmin).where(
            func.lower(SuperAdmin.email) == data.email.strip().lower(),
            SuperAdmin.ativo.is_(True),
        )
    )
    if item is None or not verify_password(data.senha, item.senha_hash):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "E-mail ou senha inválidos.",
        )

    item.ultimo_login = datetime.now(timezone.utc)
    db.commit()
    token, expires_in = create_super_admin_access_token(super_admin_id=item.id)
    return SuperAdminTokenResponse(access_token=token, expires_in=expires_in)


@router.get("/auth/me", response_model=SuperAdminOut)
def me_super_admin(
    current: SuperAdmin = Depends(get_current_super_admin),
) -> SuperAdmin:
    return current


@router.post("/auth/alterar-senha", response_model=MessageResponse)
def alterar_senha_super_admin(
    data: SuperAdminAlterarSenhaRequest,
    request: Request,
    current: SuperAdmin = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    if not verify_password(data.senha_atual, current.senha_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A senha atual está incorreta.")
    current.senha_hash = hash_password(data.nova_senha)
    current.updated_at = datetime.now(timezone.utc)
    _log(
        db,
        super_admin=current,
        request=request,
        acao="ALTEROU_PROPRIA_SENHA",
        entidade="super_admins",
        entidade_id=current.id,
    )
    db.commit()
    return MessageResponse(mensagem="Senha alterada com sucesso.")


@router.get("/dashboard", response_model=DashboardSuperAdminOut)
def dashboard_super_admin(
    current: SuperAdmin = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
) -> DashboardSuperAdminOut:
    del current
    companies = list(db.scalars(select(Empresa).order_by(Empresa.nome)))
    platforms = {
        item.empresa_id: item
        for item in db.scalars(select(EmpresaPlataforma)).all()
    }
    total_users = db.scalar(
        select(func.count(Usuario.id)).where(Usuario.ativo.is_(True))
    ) or 0
    month_start = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    appointments = db.scalar(
        select(func.count(Agendamento.id)).where(
            Agendamento.created_at >= month_start
        )
    ) or 0
    conversations = db.scalar(
        select(func.count(Conversa.id)).where(Conversa.created_at >= month_start)
    ) or 0
    active_plans = db.scalar(
        select(func.count(Plano.id)).where(Plano.ativo.is_(True))
    ) or 0

    per_plan_rows = db.execute(
        select(Plano.nome, func.count(Empresa.id))
        .outerjoin(Empresa, Empresa.plano_id == Plano.id)
        .group_by(Plano.id, Plano.nome)
        .order_by(Plano.nome)
    ).all()

    statuses = {
        company.id: platforms.get(company.id).status
        if platforms.get(company.id)
        else ("ATIVA" if company.ativo else "SUSPENSA")
        for company in companies
    }
    today = date.today()
    alerts: list[dict[str, str]] = []
    for company in companies:
        platform = platforms.get(company.id)
        if company.plano_id is None:
            alerts.append(
                {
                    "tipo": "PLANO",
                    "titulo": "Empresa sem plano",
                    "mensagem": f"{company.nome} ainda não possui um plano definido.",
                }
            )
        if platform and platform.status == "TRIAL" and platform.trial_fim:
            days = (platform.trial_fim - today).days
            if days <= 3:
                alerts.append(
                    {
                        "tipo": "TRIAL",
                        "titulo": "Teste próximo do fim",
                        "mensagem": f"{company.nome}: {max(days, 0)} dia(s) restante(s).",
                    }
                )

    return DashboardSuperAdminOut(
        empresas_total=len(companies),
        empresas_ativas=sum(1 for value in statuses.values() if value == "ATIVA"),
        empresas_trial=sum(1 for value in statuses.values() if value == "TRIAL"),
        empresas_suspensas=sum(
            1 for value in statuses.values() if value == "SUSPENSA"
        ),
        usuarios_ativos=int(total_users),
        agendamentos_mes=int(appointments),
        conversas_mes=int(conversations),
        planos_ativos=int(active_plans),
        empresas_por_plano=[
            {"plano": name, "empresas": int(count)}
            for name, count in per_plan_rows
        ],
        alertas=alerts[:12],
    )


@router.get("/planos", response_model=list[PlanoOut])
def listar_planos(
    somente_ativos: bool = False,
    current: SuperAdmin = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
) -> list[PlanoOut]:
    del current
    query = select(Plano).order_by(Plano.id)
    if somente_ativos:
        query = query.where(Plano.ativo.is_(True))
    plans = list(db.scalars(query))
    result: list[PlanoOut] = []
    for plan in plans:
        config = db.get(PlanoConfiguracao, plan.id)
        if config:
            result.append(_plan_out(plan, config))
    return result


@router.post("/planos", response_model=PlanoOut, status_code=status.HTTP_201_CREATED)
def criar_plano(
    data: PlanoCreate,
    request: Request,
    current: SuperAdmin = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
) -> PlanoOut:
    existing = db.scalar(
        select(PlanoConfiguracao).where(PlanoConfiguracao.codigo == data.codigo)
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esse código de plano já existe.")

    plan = Plano(
        nome=data.nome,
        descricao=data.descricao,
        preco=data.preco,
        ativo=data.ativo,
    )
    db.add(plan)
    db.flush()
    config = PlanoConfiguracao(
        plano_id=plan.id,
        codigo=data.codigo,
        preco_anual=data.preco_anual,
        periodo_teste_dias=data.periodo_teste_dias,
        limite_usuarios=data.limite_usuarios,
        limite_clientes=data.limite_clientes,
        limite_agendamentos_mes=data.limite_agendamentos_mes,
        limite_conversas_mes=data.limite_conversas_mes,
        limite_mensagens_ia_mes=data.limite_mensagens_ia_mes,
        limite_canais=data.limite_canais,
        limite_armazenamento_mb=data.limite_armazenamento_mb,
        ia_incluida=data.ia_incluida,
        ia_adicional_disponivel=data.ia_adicional_disponivel,
        recursos=data.recursos,
    )
    db.add(config)
    _log(
        db,
        super_admin=current,
        request=request,
        acao="CRIOU_PLANO",
        entidade="planos",
        entidade_id=plan.id,
        novos=data.model_dump(mode="json"),
    )
    db.commit()
    db.refresh(plan)
    db.refresh(config)
    return _plan_out(plan, config)


@router.patch("/planos/{plan_id}", response_model=PlanoOut)
def atualizar_plano(
    plan_id: int,
    data: PlanoUpdate,
    request: Request,
    current: SuperAdmin = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
) -> PlanoOut:
    plan, config = _get_plan(db, plan_id)
    before = _plan_out(plan, config).model_dump(mode="json")
    values = data.model_dump(exclude_unset=True)

    for field in PLAN_FIELDS:
        if field in values:
            setattr(plan, field, values[field])
    for field in CONFIG_FIELDS:
        if field in values:
            setattr(config, field, values[field])
    config.updated_at = datetime.now(timezone.utc)

    _log(
        db,
        super_admin=current,
        request=request,
        acao="ATUALIZOU_PLANO",
        entidade="planos",
        entidade_id=plan.id,
        anteriores=before,
        novos=values,
    )
    db.commit()
    db.refresh(plan)
    db.refresh(config)
    return _plan_out(plan, config)


@router.get("/empresas", response_model=list[EmpresaResumoOut])
def listar_empresas(
    busca: str | None = None,
    status_empresa: str | None = None,
    plano_id: int | None = None,
    limit: int = Query(100, ge=1, le=300),
    current: SuperAdmin = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
) -> list[EmpresaResumoOut]:
    del current
    query = select(Empresa).order_by(Empresa.nome).limit(limit)
    if busca:
        term = f"%{busca.strip().lower()}%"
        query = query.where(
            func.lower(Empresa.nome).like(term)
            | func.lower(Empresa.cnpj).like(term)
            | func.lower(func.coalesce(Empresa.email, "")).like(term)
        )
    if plano_id:
        query = query.where(Empresa.plano_id == plano_id)
    companies = list(db.scalars(query))
    summaries = [_company_summary(db, company) for company in companies]
    if status_empresa:
        summaries = [item for item in summaries if item.status == status_empresa]
    db.commit()
    return summaries


@router.post(
    "/empresas",
    response_model=EmpresaDetalheOut,
    status_code=status.HTTP_201_CREATED,
)
def criar_empresa(
    data: EmpresaSuperAdminCreate,
    request: Request,
    current: SuperAdmin = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
) -> EmpresaDetalheOut:
    plan, _ = _get_plan(db, data.plano_id)
    if not plan.ativo:
        raise HTTPException(status.HTTP_409_CONFLICT, "O plano selecionado está inativo.")
    if db.scalar(select(Empresa).where(Empresa.cnpj == data.cnpj)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Esse CNPJ já está cadastrado.")

    company = Empresa(
        nome=data.nome,
        cnpj=data.cnpj,
        telefone=data.telefone,
        email=data.email,
        cidade=data.cidade,
        estado=data.estado.upper() if data.estado else None,
        timezone=data.timezone,
        plano_id=data.plano_id,
        ativo=True,
    )
    db.add(company)
    db.flush()

    trial_end = (
        date.today() + timedelta(days=data.periodo_teste_dias)
        if data.periodo_teste_dias > 0
        else None
    )
    platform = EmpresaPlataforma(
        empresa_id=company.id,
        status="TRIAL" if trial_end else "ATIVA",
        trial_fim=trial_end,
        recursos_personalizados={},
        limites_personalizados={},
    )
    db.add(platform)
    db.add(
        Assinatura(
            empresa_id=company.id,
            plano_id=plan.id,
            status=StatusAssinatura.TRIAL if trial_end else StatusAssinatura.ATIVA,
            data_inicio=date.today(),
            data_vencimento=trial_end,
        )
    )
    db.add(
        Usuario(
            empresa_id=company.id,
            nome=data.admin_nome,
            email=data.admin_email.strip().lower(),
            senha_hash=hash_password(data.admin_senha),
            cargo=CargoUsuario.ADMIN,
            ativo=True,
        )
    )
    _log(
        db,
        super_admin=current,
        request=request,
        acao="CRIOU_EMPRESA",
        entidade="empresas",
        entidade_id=company.id,
        empresa_id=company.id,
        novos={
            "nome": company.nome,
            "cnpj": company.cnpj,
            "plano_id": plan.id,
            "trial_fim": trial_end.isoformat() if trial_end else None,
            "admin_email": data.admin_email.strip().lower(),
        },
    )
    db.commit()
    db.refresh(company)
    return obter_empresa(company.id, current, db)


@router.get("/empresas/{empresa_id}", response_model=EmpresaDetalheOut)
def obter_empresa(
    empresa_id: int,
    current: SuperAdmin = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
) -> EmpresaDetalheOut:
    del current
    company = db.get(Empresa, empresa_id)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa não encontrada.")
    platform = _get_platform(db, company)
    policy = get_effective_plan(db, company.id)
    usage = get_company_usage(db, company.id)
    plan = db.get(Plano, company.plano_id) if company.plano_id else None
    db.commit()
    return EmpresaDetalheOut(
        id=company.id,
        nome=company.nome,
        cnpj=company.cnpj,
        telefone=company.telefone,
        email=company.email,
        cidade=company.cidade,
        estado=company.estado,
        timezone=company.timezone,
        ativo=company.ativo,
        status=platform.status,
        plano_id=company.plano_id,
        plano_nome=plan.nome if plan else None,
        trial_fim=platform.trial_fim,
        recursos_personalizados=platform.recursos_personalizados or {},
        limites_personalizados=platform.limites_personalizados or {},
        ia_adicional_ativo=platform.ia_adicional_ativo,
        ia_limite_adicional=platform.ia_limite_adicional,
        observacoes=platform.observacoes,
        uso={
            "usuarios_ativos": usage["usuarios"],
            "clientes": usage["clientes"],
            "agendamentos_mes": usage["agendamentos_mes"],
            "conversas_mes": usage["conversas_mes"],
            "canais_ativos": usage["canais"],
            "mensagens_ia_mes": usage["mensagens_ia_mes"],
            "limites": policy.limites,
            "recursos": policy.recursos,
        },
        created_at=company.created_at,
        updated_at=company.updated_at,
    )


@router.patch("/empresas/{empresa_id}", response_model=EmpresaDetalheOut)
def atualizar_empresa(
    empresa_id: int,
    data: EmpresaSuperAdminUpdate,
    request: Request,
    current: SuperAdmin = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
) -> EmpresaDetalheOut:
    company = db.get(Empresa, empresa_id)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa não encontrada.")
    platform = _get_platform(db, company)
    before = {
        "plano_id": company.plano_id,
        "status": platform.status,
        "trial_fim": platform.trial_fim.isoformat() if platform.trial_fim else None,
        "recursos_personalizados": platform.recursos_personalizados,
        "limites_personalizados": platform.limites_personalizados,
        "ia_adicional_ativo": platform.ia_adicional_ativo,
        "ia_limite_adicional": platform.ia_limite_adicional,
        "observacoes": platform.observacoes,
    }
    values = data.model_dump(exclude_unset=True)

    if "plano_id" in values:
        plan, config = _get_plan(db, values["plano_id"])
        if not plan.ativo:
            raise HTTPException(status.HTTP_409_CONFLICT, "O plano está inativo.")
        company.plano_id = plan.id
        subscription = _current_subscription(db, company.id)
        if subscription is None:
            subscription = Assinatura(
                empresa_id=company.id,
                plano_id=plan.id,
                status=StatusAssinatura.ATIVA,
                data_inicio=date.today(),
            )
            db.add(subscription)
        else:
            subscription.plano_id = plan.id
        if platform.status == "TRIAL" and not platform.trial_fim:
            platform.trial_fim = date.today() + timedelta(
                days=config.periodo_teste_dias
            )

    if "status" in values:
        platform.status = values["status"]
        company.ativo = values["status"] in {"TRIAL", "ATIVA"}
        subscription = _current_subscription(db, company.id)
        if subscription:
            status_map = {
                "TRIAL": StatusAssinatura.TRIAL,
                "ATIVA": StatusAssinatura.ATIVA,
                "SUSPENSA": StatusAssinatura.INADIMPLENTE,
                "CANCELADA": StatusAssinatura.CANCELADA,
                "ARQUIVADA": StatusAssinatura.CANCELADA,
            }
            subscription.status = status_map[values["status"]]

    for field in {
        "trial_fim",
        "recursos_personalizados",
        "limites_personalizados",
        "ia_adicional_ativo",
        "ia_limite_adicional",
        "observacoes",
    }:
        if field in values:
            setattr(platform, field, values[field])

    if platform.ia_adicional_ativo and company.plano_id:
        _, config = _get_plan(db, company.plano_id)
        if not config.ia_adicional_disponivel and not config.ia_incluida:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "O plano não permite contratar IA como adicional.",
            )

    platform.updated_at = datetime.now(timezone.utc)
    _log(
        db,
        super_admin=current,
        request=request,
        acao="ATUALIZOU_EMPRESA_PLATAFORMA",
        entidade="empresas",
        entidade_id=company.id,
        empresa_id=company.id,
        anteriores=before,
        novos=data.model_dump(exclude_unset=True, mode="json"),
    )
    db.commit()
    return obter_empresa(company.id, current, db)


@router.get(
    "/empresas/{empresa_id}/ia",
    response_model=ConfigIASuperAdminOut | None,
)
def obter_ia_empresa(
    empresa_id: int,
    current: SuperAdmin = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
) -> ConfigIA | None:
    del current
    if db.get(Empresa, empresa_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa não encontrada.")
    return db.scalar(select(ConfigIA).where(ConfigIA.empresa_id == empresa_id))


@router.put(
    "/empresas/{empresa_id}/ia",
    response_model=ConfigIASuperAdminOut,
)
def salvar_ia_empresa(
    empresa_id: int,
    data: ConfigIASuperAdminUpdate,
    request: Request,
    current: SuperAdmin = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
) -> ConfigIA:
    company = db.get(Empresa, empresa_id)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa não encontrada.")
    item = db.scalar(select(ConfigIA).where(ConfigIA.empresa_id == empresa_id))
    before = None
    if item is None:
        item = ConfigIA(empresa_id=empresa_id)
        db.add(item)
        db.flush()
    else:
        before = {
            "nome_assistente": item.nome_assistente,
            "mensagem_boas_vindas": item.mensagem_boas_vindas,
            "prompt": item.prompt,
            "temperatura": str(item.temperatura),
        }
    item.nome_assistente = data.nome_assistente
    item.mensagem_boas_vindas = data.mensagem_boas_vindas
    item.prompt = data.prompt
    item.temperatura = Decimal(data.temperatura)
    _log(
        db,
        super_admin=current,
        request=request,
        acao="ATUALIZOU_IA_EMPRESA",
        entidade="config_ia",
        entidade_id=item.id,
        empresa_id=empresa_id,
        anteriores=before,
        novos=data.model_dump(mode="json"),
    )
    db.commit()
    db.refresh(item)
    return item


@router.get("/auditoria", response_model=list[SuperAdminLogOut])
def listar_auditoria(
    empresa_id: int | None = None,
    acao: str | None = None,
    limit: int = Query(100, ge=1, le=300),
    current: SuperAdmin = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
) -> list[SuperAdminLog]:
    del current
    query = select(SuperAdminLog).order_by(SuperAdminLog.created_at.desc())
    if empresa_id:
        query = query.where(SuperAdminLog.empresa_id == empresa_id)
    if acao:
        query = query.where(SuperAdminLog.acao == acao)
    return list(db.scalars(query.limit(limit)))
