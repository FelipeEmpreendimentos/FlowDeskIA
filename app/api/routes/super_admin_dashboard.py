from datetime import date, datetime, time, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.super_admin_deps import get_current_super_admin
from app.database.database import get_db
from app.models.enums import StatusAssinatura
from app.models.models import Agendamento, Assinatura, Conversa, Empresa, Plano, Usuario
from app.models.platform import EmpresaPlataforma, SuperAdmin, SuperAdminLog
from app.schemas.super_admin_dashboard import (
    SuperAdminDashboardAlert,
    SuperAdminDashboardAudit,
    SuperAdminFinancialDashboardOut,
)


router = APIRouter(prefix="/super-admin", tags=["Super Admin Dashboard"])


def _period(start_date: date | None, end_date: date | None) -> tuple[date, date]:
    today = date.today()
    start = start_date or today.replace(day=1)
    end = end_date or today
    return (end, start) if start > end else (start, end)


def _bounds(start: date, end: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(start, time.min, tzinfo=timezone.utc),
        datetime.combine(end, time.max, tzinfo=timezone.utc),
    )


@router.get("/dashboard-financeiro", response_model=SuperAdminFinancialDashboardOut)
def financial_dashboard(
    data_inicio: date | None = None,
    data_fim: date | None = None,
    current: SuperAdmin = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
) -> SuperAdminFinancialDashboardOut:
    del current
    start, end = _period(data_inicio, data_fim)
    start_dt, end_dt = _bounds(start, end)

    companies = list(db.scalars(select(Empresa).order_by(Empresa.nome)))
    platforms = {
        item.empresa_id: item
        for item in db.scalars(select(EmpresaPlataforma)).all()
    }
    plans = {item.id: item for item in db.scalars(select(Plano)).all()}

    subscriptions = list(
        db.scalars(
            select(Assinatura).order_by(
                Assinatura.empresa_id,
                Assinatura.created_at.desc(),
            )
        )
    )
    latest_subscription: dict[int, Assinatura] = {}
    for subscription in subscriptions:
        latest_subscription.setdefault(subscription.empresa_id, subscription)

    statuses = {
        company.id: (
            platforms[company.id].status
            if company.id in platforms
            else ("ATIVA" if company.ativo else "SUSPENSA")
        )
        for company in companies
    }

    active_companies = [
        company for company in companies if statuses[company.id] == "ATIVA"
    ]
    estimated_mrr = sum(
        (
            Decimal(plans[company.plano_id].preco)
            for company in active_companies
            if company.plano_id in plans
        ),
        Decimal("0.00"),
    )

    new_contracts = [
        subscription
        for subscription in subscriptions
        if start <= subscription.data_inicio <= end
        and subscription.status in {StatusAssinatura.ATIVA, StatusAssinatura.TRIAL}
    ]
    new_contract_value = sum(
        (
            Decimal(plans[subscription.plano_id].preco)
            for subscription in new_contracts
            if subscription.plano_id in plans
        ),
        Decimal("0.00"),
    )

    appointments = int(
        db.scalar(
            select(func.count(Agendamento.id)).where(
                Agendamento.data >= start,
                Agendamento.data <= end,
            )
        )
        or 0
    )
    conversations = int(
        db.scalar(
            select(func.count(Conversa.id)).where(
                Conversa.created_at >= start_dt,
                Conversa.created_at <= end_dt,
            )
        )
        or 0
    )
    active_users = int(
        db.scalar(select(func.count(Usuario.id)).where(Usuario.ativo.is_(True))) or 0
    )
    active_plans = int(
        db.scalar(select(func.count(Plano.id)).where(Plano.ativo.is_(True))) or 0
    )
    new_companies = sum(
        1 for company in companies if start_dt <= company.created_at <= end_dt
    )
    overdue = sum(
        1
        for subscription in latest_subscription.values()
        if subscription.status == StatusAssinatura.INADIMPLENTE
    )
    ai_addons = sum(
        1 for platform in platforms.values() if platform.ia_adicional_ativo
    )

    per_plan_rows = db.execute(
        select(Plano.nome, func.count(Empresa.id))
        .outerjoin(Empresa, Empresa.plano_id == Plano.id)
        .group_by(Plano.id, Plano.nome)
        .order_by(Plano.nome)
    ).all()

    recent_logs = list(
        db.scalars(
            select(SuperAdminLog)
            .where(
                SuperAdminLog.created_at >= start_dt,
                SuperAdminLog.created_at <= end_dt,
            )
            .order_by(SuperAdminLog.created_at.desc())
            .limit(8)
        )
    )
    audit_count = int(
        db.scalar(
            select(func.count(SuperAdminLog.id)).where(
                SuperAdminLog.created_at >= start_dt,
                SuperAdminLog.created_at <= end_dt,
            )
        )
        or 0
    )

    alerts: list[SuperAdminDashboardAlert] = []
    today = date.today()
    for company in companies:
        platform = platforms.get(company.id)
        subscription = latest_subscription.get(company.id)
        if company.plano_id is None:
            alerts.append(
                SuperAdminDashboardAlert(
                    type="PLAN",
                    title="Empresa sem plano",
                    message=f"{company.nome} ainda não possui um plano definido.",
                )
            )
        if subscription and subscription.status == StatusAssinatura.INADIMPLENTE:
            alerts.append(
                SuperAdminDashboardAlert(
                    type="OVERDUE",
                    title="Assinatura inadimplente",
                    message=f"{company.nome} precisa de acompanhamento financeiro.",
                )
            )
        if platform and platform.status == "TRIAL" and platform.trial_fim:
            days = (platform.trial_fim - today).days
            if days <= 3:
                alerts.append(
                    SuperAdminDashboardAlert(
                        type="TRIAL",
                        title="Teste próximo do fim",
                        message=f"{company.nome}: {max(days, 0)} dia(s) restante(s).",
                    )
                )

    return SuperAdminFinancialDashboardOut(
        start_date=start,
        end_date=end,
        companies_total=len(companies),
        companies_active=len(active_companies),
        companies_trial=sum(1 for value in statuses.values() if value == "TRIAL"),
        companies_suspended=sum(
            1 for value in statuses.values() if value == "SUSPENSA"
        ),
        companies_overdue=overdue,
        new_companies_period=new_companies,
        active_users=active_users,
        appointments_period=appointments,
        conversations_period=conversations,
        active_plans=active_plans,
        active_ai_addons=ai_addons,
        estimated_mrr=estimated_mrr,
        estimated_arr=estimated_mrr * Decimal("12"),
        new_contracts_period=len(new_contracts),
        new_contracts_monthly_value=new_contract_value,
        audit_events_period=audit_count,
        companies_by_plan=[
            {"plano": name, "empresas": int(count)}
            for name, count in per_plan_rows
        ],
        alerts=alerts[:12],
        recent_audit=[
            SuperAdminDashboardAudit(
                id=item.id,
                action=item.acao,
                entity=item.entidade,
                company_id=item.empresa_id,
                created_at=item.created_at,
            )
            for item in recent_logs
        ],
    )
