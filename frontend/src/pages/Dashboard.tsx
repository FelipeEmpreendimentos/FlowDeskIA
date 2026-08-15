import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router";
import { Icon } from "../components/Icon";
import { OnboardingChecklist } from "../components/OnboardingChecklist";
import { Alert, LoadingState, PageHeader, StatusBadge } from "../components/UI";
import { apiRequest } from "../services/api";
import type {
  AppOutletContext,
  DashboardResumo,
  Notificacao,
} from "../types";
import { formatDateTime, formatTime } from "../utils/format";

const resumoVazio: DashboardResumo = {
  agendamentos_hoje: 0,
  agendamentos_pendentes: 0,
  conversas_abertas: 0,
  clientes_ativos: 0,
  notificacoes_nao_lidas: 0,
};

interface DashboardReferencia {
  id: number;
  nome: string;
}

interface DashboardAgendamento {
  id: number;
  cliente_id: number;
  servico_id: number;
  hora_inicio: string;
  status: string;
}

interface DashboardBootstrap {
  resumo: DashboardResumo;
  agendamentos: DashboardAgendamento[];
  clientes: DashboardReferencia[];
  servicos: DashboardReferencia[];
  notificacoes: Notificacao[];
}

export function Dashboard() {
  const { usuario } = useOutletContext<AppOutletContext>();
  const [resumo, setResumo] = useState(resumoVazio);
  const [agendamentos, setAgendamentos] = useState<DashboardAgendamento[]>([]);
  const [clientes, setClientes] = useState<DashboardReferencia[]>([]);
  const [servicos, setServicos] = useState<DashboardReferencia[]>([]);
  const [notificacoes, setNotificacoes] = useState<Notificacao[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");

  useEffect(() => {
    let ativo = true;
    let carregamentoEmAndamento = false;

    async function carregar() {
      if (carregamentoEmAndamento) return;
      carregamentoEmAndamento = true;

      try {
        const today = new Date();
        const iso = new Date(today.getTime() - today.getTimezoneOffset() * 60_000)
          .toISOString()
          .slice(0, 10);
        const dados = await apiRequest<DashboardBootstrap>(
          `/administrativo/dashboard/bootstrap?data=${iso}`,
        );

        if (!ativo) return;

        setResumo(dados.resumo);
        setAgendamentos(dados.agendamentos);
        setClientes(dados.clientes);
        setServicos(dados.servicos);
        setNotificacoes(dados.notificacoes);
        setErro("");
      } catch (error) {
        if (!ativo) return;
        setErro(error instanceof Error ? error.message : "Não foi possível carregar o painel.");
      } finally {
        carregamentoEmAndamento = false;
        if (ativo) setCarregando(false);
      }
    }

    void carregar();

    function atualizarAoRetornar() {
      if (document.visibilityState === "visible") {
        void carregar();
      }
    }

    window.addEventListener("focus", atualizarAoRetornar);
    document.addEventListener("visibilitychange", atualizarAoRetornar);

    return () => {
      ativo = false;
      window.removeEventListener("focus", atualizarAoRetornar);
      document.removeEventListener("visibilitychange", atualizarAoRetornar);
    };
  }, []);

  const clienteNome = (id: number) =>
    clientes.find((item) => item.id === id)?.nome ?? `Cliente #${id}`;
  const servicoNome = (id: number) =>
    servicos.find((item) => item.id === id)?.nome ?? `Serviço #${id}`;

  return (
    <div className="page">
      <PageHeader
        eyebrow="Painel administrativo"
        title={`Olá, ${usuario.nome}`}
        description="Acompanhe os principais números da sua operação."
        actions={
          <Link className="user-chip" to="/configuracoes">
            <span className="user-avatar">{usuario.nome.charAt(0).toUpperCase()}</span>
            <span>
              <strong>{usuario.nome}</strong>
              <small>{usuario.cargo}</small>
            </span>
          </Link>
        }
      />

      <OnboardingChecklist ativo={usuario.cargo === "ADMIN"} />

      {carregando && <LoadingState label="Carregando visão geral..." />}
      {erro && <Alert>{erro}</Alert>}

      {!carregando && !erro && (
        <>
          <section className="metrics-grid">
            <article className="metric-card">
              <span>Agendamentos hoje</span>
              <strong>{resumo.agendamentos_hoje}</strong>
              <small>Serviços previstos para hoje</small>
            </article>
            <article className="metric-card">
              <span>Agendamentos pendentes</span>
              <strong>{resumo.agendamentos_pendentes}</strong>
              <small>Aguardando confirmação</small>
            </article>
            <article className="metric-card">
              <span>Conversas abertas</span>
              <strong>{resumo.conversas_abertas}</strong>
              <small>Clientes aguardando atendimento</small>
            </article>
            <article className="metric-card">
              <span>Clientes ativos</span>
              <strong>{resumo.clientes_ativos}</strong>
              <small>Total na base da empresa</small>
            </article>
          </section>

          <section className="dashboard-grid">
            <article className="content-card">
              <div className="card-heading">
                <div>
                  <span>Agenda de hoje</span>
                  <h2>Próximos atendimentos</h2>
                </div>
                <Link className="text-link" to="/agenda">
                  Ver agenda
                </Link>
              </div>

              {agendamentos.length === 0 ? (
                <div className="compact-empty">Nenhum próximo atendimento para hoje.</div>
              ) : (
                <div className="appointment-list">
                  {agendamentos.map((item) => (
                    <div className="appointment-row" key={item.id}>
                      <span className="appointment-time">{formatTime(item.hora_inicio)}</span>
                      <div>
                        <strong>{clienteNome(item.cliente_id)}</strong>
                        <small>{servicoNome(item.servico_id)}</small>
                      </div>
                      <StatusBadge value={item.status} />
                    </div>
                  ))}
                </div>
              )}
            </article>

            <article className="content-card">
              <div className="card-heading">
                <div>
                  <span>Acesso rápido</span>
                  <h2>Comece por aqui</h2>
                </div>
              </div>
              <div className="quick-action-grid">
                <Link to="/agenda?novo=1">
                  <Icon name="calendar" />
                  <span>Novo agendamento</span>
                </Link>
                <Link to="/clientes?novo=1">
                  <Icon name="users" />
                  <span>Cadastrar cliente</span>
                </Link>
                <Link to="/conversas">
                  <Icon name="chat" />
                  <span>Abrir conversas</span>
                </Link>
                <Link to="/servicos">
                  <Icon name="services" />
                  <span>Gerenciar serviços</span>
                </Link>
              </div>
            </article>
          </section>

          <section className="content-card notifications-preview">
            <div className="card-heading">
              <div>
                <span>Central de atenção</span>
                <h2>Notificações recentes</h2>
              </div>
              <Link className="number-pill" to="/notificacoes">
                {resumo.notificacoes_nao_lidas}
              </Link>
            </div>

            {notificacoes.length === 0 ? (
              <div className="compact-empty">Tudo certo. Nenhuma notificação pendente.</div>
            ) : (
              <div className="notification-list">
                {notificacoes.map((item) => (
                  <div className="notification-item" key={item.id}>
                    <span className="notification-icon">
                      <Icon name="bell" size={18} />
                    </span>
                    <div>
                      <strong>{item.titulo}</strong>
                      <p>{item.mensagem}</p>
                      <small>{formatDateTime(item.created_at)}</small>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
