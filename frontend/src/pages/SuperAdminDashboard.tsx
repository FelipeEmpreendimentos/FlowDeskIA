import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router";
import { Icon } from "../components/Icon";
import {
  superAdminApiRequest,
  superAdminBuildQuery,
} from "../services/superAdminApi";
import type {
  SuperAdminFinancialDashboard,
  SuperAdminOutletContext,
} from "../types/superAdmin";
import {
  formatCurrency,
  formatDateTime,
  todayISO,
} from "../utils/format";

function firstDayOfMonth(): string {
  return `${todayISO().slice(0, 7)}-01`;
}

function shiftDate(iso: string, days: number): string {
  const [year, month, day] = iso.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  date.setDate(date.getDate() + days);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

function firstDayOfWeek(): string {
  const today = todayISO();
  const [year, month, day] = today.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  const weekday = date.getDay();
  return shiftDate(today, weekday === 0 ? -6 : 1 - weekday);
}

const emptyDashboard: SuperAdminFinancialDashboard = {
  start_date: firstDayOfMonth(),
  end_date: todayISO(),
  companies_total: 0,
  companies_active: 0,
  companies_trial: 0,
  companies_suspended: 0,
  companies_overdue: 0,
  new_companies_period: 0,
  active_users: 0,
  appointments_period: 0,
  conversations_period: 0,
  active_plans: 0,
  active_ai_addons: 0,
  estimated_mrr: 0,
  estimated_arr: 0,
  new_contracts_period: 0,
  new_contracts_monthly_value: 0,
  audit_events_period: 0,
  companies_by_plan: [],
  alerts: [],
  recent_audit: [],
};

export function SuperAdminDashboard() {
  const { usuario } = useOutletContext<SuperAdminOutletContext>();
  const [startDate, setStartDate] = useState(firstDayOfMonth());
  const [endDate, setEndDate] = useState(todayISO());
  const [data, setData] = useState<SuperAdminFinancialDashboard>(emptyDashboard);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setData(
        await superAdminApiRequest<SuperAdminFinancialDashboard>(
          `/dashboard-financeiro${superAdminBuildQuery({
            data_inicio: startDate,
            data_fim: endDate,
          })}`,
        ),
      );
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Não foi possível carregar o painel.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [startDate, endDate]);

  function setPeriod(start: string, end: string) {
    setStartDate(start);
    setEndDate(end);
  }

  return (
    <div className="super-admin-page">
      <header className="super-admin-page-header">
        <div>
          <span>Plataforma FlowDeskIA</span>
          <h1>Olá, {usuario.nome}</h1>
          <p>Acompanhe receita contratada, crescimento, uso e pontos de atenção.</p>
        </div>
        <Link className="super-admin-primary-button" to="/super-admin/empresas">
          <Icon name="building" size={18} />
          Gerenciar empresas
        </Link>
      </header>

      <section className="super-admin-card super-admin-dashboard-filters">
        <label>
          Data inicial
          <input
            type="date"
            value={startDate}
            max={endDate}
            onChange={(event) => setStartDate(event.target.value)}
          />
        </label>
        <label>
          Data final
          <input
            type="date"
            value={endDate}
            min={startDate}
            onChange={(event) => setEndDate(event.target.value)}
          />
        </label>
        <div className="super-admin-period-shortcuts">
          <button type="button" onClick={() => setPeriod(todayISO(), todayISO())}>
            Hoje
          </button>
          <button type="button" onClick={() => setPeriod(firstDayOfWeek(), todayISO())}>
            Esta semana
          </button>
          <button type="button" onClick={() => setPeriod(firstDayOfMonth(), todayISO())}>
            Este mês
          </button>
        </div>
        <button className="super-admin-secondary-button" type="button" onClick={() => void load()}>
          <Icon name="refresh" size={16} />
          Atualizar
        </button>
      </section>

      {loading && <div className="super-admin-state">Calculando visão geral...</div>}
      {error && <div className="super-admin-alert error">{error}</div>}

      {!loading && !error && (
        <>
          <section className="super-admin-financial-highlight-grid">
            <article>
              <span>Receita mensal contratada</span>
              <strong>{formatCurrency(data.estimated_mrr)}</strong>
              <small>Estimativa pelos planos das empresas ativas</small>
            </article>
            <article>
              <span>Receita anual projetada</span>
              <strong>{formatCurrency(data.estimated_arr)}</strong>
              <small>Projeção de 12 meses, sem considerar cancelamentos</small>
            </article>
            <article>
              <span>Novos contratos no período</span>
              <strong>{data.new_contracts_period}</strong>
              <small>{formatCurrency(data.new_contracts_monthly_value)} em valor mensal</small>
            </article>
            <article>
              <span>Adicionais de IA ativos</span>
              <strong>{data.active_ai_addons}</strong>
              <small>Empresas com IA contratada separadamente</small>
            </article>
          </section>

          <section className="super-admin-metrics-grid super-admin-operational-metrics">
            <article><span>Empresas</span><strong>{data.companies_total}</strong><small>{data.new_companies_period} novas no período</small></article>
            <article><span>Ativas</span><strong>{data.companies_active}</strong><small>Assinaturas em operação</small></article>
            <article><span>Em teste</span><strong>{data.companies_trial}</strong><small>Período gratuito</small></article>
            <article><span>Inadimplentes</span><strong>{data.companies_overdue}</strong><small>Precisam de acompanhamento</small></article>
            <article><span>Suspensas</span><strong>{data.companies_suspended}</strong><small>Acesso bloqueado</small></article>
            <article><span>Usuários ativos</span><strong>{data.active_users}</strong><small>Em todas as empresas</small></article>
            <article><span>Agendamentos</span><strong>{data.appointments_period}</strong><small>No período selecionado</small></article>
            <article><span>Conversas</span><strong>{data.conversations_period}</strong><small>No período selecionado</small></article>
          </section>

          <section className="super-admin-dashboard-grid">
            <article className="super-admin-card">
              <div className="super-admin-card-heading">
                <div><span>Distribuição</span><h2>Empresas por plano</h2></div>
                <Link to="/super-admin/planos">Editar planos</Link>
              </div>
              {data.companies_by_plan.length === 0 ? (
                <div className="super-admin-empty">Nenhum plano com empresa vinculada.</div>
              ) : (
                <div className="super-admin-plan-distribution">
                  {data.companies_by_plan.map((item) => (
                    <div key={item.plano}>
                      <span>{item.plano}</span>
                      <strong>{item.empresas}</strong>
                    </div>
                  ))}
                </div>
              )}
            </article>

            <article className="super-admin-card">
              <div className="super-admin-card-heading">
                <div><span>Central de atenção</span><h2>Alertas</h2></div>
                <Icon name="bell" size={22} />
              </div>
              {data.alerts.length === 0 ? (
                <div className="super-admin-empty">Tudo certo. Nenhum alerta pendente.</div>
              ) : (
                <div className="super-admin-alert-list">
                  {data.alerts.map((alert, index) => (
                    <div key={`${alert.type}-${index}`}>
                      <span><Icon name="bell" size={16} /></span>
                      <div><strong>{alert.title}</strong><p>{alert.message}</p></div>
                    </div>
                  ))}
                </div>
              )}
            </article>
          </section>

          <section className="super-admin-card super-admin-dashboard-audit">
            <div className="super-admin-card-heading">
              <div>
                <span>Controle</span>
                <h2>Auditoria recente</h2>
              </div>
              <Link to="/super-admin/auditoria">
                {data.audit_events_period} eventos no período
              </Link>
            </div>
            {data.recent_audit.length === 0 ? (
              <div className="super-admin-empty">Nenhuma ação administrativa no período.</div>
            ) : (
              <div className="super-admin-dashboard-audit-list">
                {data.recent_audit.map((item) => (
                  <article key={item.id}>
                    <span><Icon name="clock" size={16} /></span>
                    <div>
                      <strong>{item.action.replaceAll("_", " ")}</strong>
                      <small>
                        {item.entity ?? "Plataforma"}
                        {item.company_id ? ` · Empresa #${item.company_id}` : ""}
                        {` · ${formatDateTime(item.created_at)}`}
                      </small>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
