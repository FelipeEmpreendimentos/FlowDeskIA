from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class SuperAdminDashboardAlert(BaseModel):
    type: str
    title: str
    message: str


class SuperAdminDashboardAudit(BaseModel):
    id: int
    action: str
    entity: str | None
    company_id: int | None
    created_at: datetime


class SuperAdminFinancialDashboardOut(BaseModel):
    start_date: date
    end_date: date
    companies_total: int
    companies_active: int
    companies_trial: int
    companies_suspended: int
    companies_overdue: int
    new_companies_period: int
    active_users: int
    appointments_period: int
    conversations_period: int
    active_plans: int
    active_ai_addons: int
    estimated_mrr: Decimal
    estimated_arr: Decimal
    new_contracts_period: int
    new_contracts_monthly_value: Decimal
    audit_events_period: int
    companies_by_plan: list[dict[str, int | str]]
    alerts: list[SuperAdminDashboardAlert]
    recent_audit: list[SuperAdminDashboardAudit]
