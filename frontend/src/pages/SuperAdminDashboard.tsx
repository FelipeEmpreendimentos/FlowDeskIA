import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router";
import { Icon } from "../components/Icon";
import { superAdminApiRequest } from "../services/superAdminApi";
import type {
  SuperAdminDashboard as DashboardData,
  SuperAdminOutletContext,
} from "../types/superAdmin";

const emptyDashboard: DashboardData = {
  empresas_total: 0,
  empresas_ativas: 0,
  empresas_trial: 0,
  empresas_suspensas: 0,
  usuarios_ativos: 0,
  agendamentos_mes: 0,
  conversas_mes: 0,
  planos_ativos: 0,
  empresas_por_plano: [],
  alertas: [],
};

export function SuperAdminDashboard() {
  const { usuario } = useOutletContext<SuperAdminOutletContext>();
  const [dados, setDados] = useState<DashboardData>(emptyDashboard);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");

  useEffect(() => {
    async function carregar() {
      try {
        setDados(await superAdminApiRequest<DashboardData>("/dashboard"));
      } catch (error) {
        setErro(
          error instanceof Error
            ? error.message
            : "Não foi possível carregar o painel.",
        );
      } finally {
        setCarregando(false);
      }
    }
    void carregar();
  }, []);

  return (
    <div className="super-admin-page">
      <header className="super-admin-page-header">
        <div>
          <span>Plataforma FlowDeskIA</span>
          <h1>Olá, {usuario.nome}</h1>
          <p>Acompanhe empresas, planos e uso da plataforma.</p>
        </div>
        <Link className="super-admin-primary-button" to="/super-admin/empresas">
          <Icon name="building" size={18} />
          Gerenciar empresas
        </Link>
      </header>

      {carregando && <div className="super-admin-state">Carregando visão geral...</div>}
      {erro && <div className="super-admin-alert error">{erro}</div>}

      {!carregando && !erro && (
        <>
          <section className="super-admin-metrics-grid">
            <article><span>Empresas</span><strong>{dados.empresas_total}</strong><small>Total cadastrado</small></article>
            <article><span>Ativas</span><strong>{dados.empresas_ativas}</strong><small>Assinaturas em operação</small></article>
            <article><span>Em teste</span><strong>{dados.empresas_trial}</strong><small>Período gratuito</small></article>
            <article><span>Suspensas</span><strong>{dados.empresas_suspensas}</strong><small>Acesso bloqueado</small></article>
            <article><span>Usuários ativos</span><strong>{dados.usuarios_ativos}</strong><small>Em todas as empresas</small></article>
            <article><span>Agendamentos no mês</span><strong>{dados.agendamentos_mes}</strong><small>Uso atual da plataforma</small></article>
            <article><span>Conversas no mês</span><strong>{dados.conversas_mes}</strong><small>Atendimentos iniciados</small></article>
            <article><span>Planos ativos</span><strong>{dados.planos_ativos}</strong><small>Disponíveis para venda</small></article>
          </section>

          <section className="super-admin-dashboard-grid">
            <article className="super-admin-card">
              <div className="super-admin-card-heading">
                <div><span>Distribuição</span><h2>Empresas por plano</h2></div>
                <Link to="/super-admin/planos">Editar planos</Link>
              </div>
              {dados.empresas_por_plano.length === 0 ? (
                <div className="super-admin-empty">Nenhum plano com empresa vinculada.</div>
              ) : (
                <div className="super-admin-plan-distribution">
                  {dados.empresas_por_plano.map((item) => (
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
              {dados.alertas.length === 0 ? (
                <div className="super-admin-empty">Tudo certo. Nenhum alerta pendente.</div>
              ) : (
                <div className="super-admin-alert-list">
                  {dados.alertas.map((alerta, index) => (
                    <div key={`${alerta.tipo}-${index}`}>
                      <span><Icon name="bell" size={16} /></span>
                      <div><strong>{alerta.titulo}</strong><p>{alerta.mensagem}</p></div>
                    </div>
                  ))}
                </div>
              )}
            </article>
          </section>
        </>
      )}
    </div>
  );
}
