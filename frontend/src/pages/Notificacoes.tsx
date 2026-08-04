import { useEffect, useState, type FormEvent } from "react";
import { Icon } from "../components/Icon";
import { Alert, EmptyState, LoadingState, PageHeader } from "../components/UI";
import { apiRequest } from "../services/api";
import type { Notificacao } from "../types";
import { formatDateTime } from "../utils/format";

interface Preferencias {
  id: number;
  empresa_id: number;
  usuario_id: number;
  agendamentos: boolean;
  financeiro: boolean;
  conversas: boolean;
  avaliacoes: boolean;
  integracoes: boolean;
  planos_limites: boolean;
  sistema: boolean;
  updated_at: string;
}

type ChavePreferencia =
  | "agendamentos"
  | "financeiro"
  | "conversas"
  | "avaliacoes"
  | "integracoes"
  | "planos_limites"
  | "sistema";

const opcoes: Array<{
  chave: ChavePreferencia;
  titulo: string;
  descricao: string;
  icon: "calendar" | "finance" | "chat" | "check" | "settings" | "lock" | "bell";
}> = [
  {
    chave: "agendamentos",
    titulo: "Agendamentos",
    descricao: "Criações, alterações, cancelamentos e atendimentos atribuídos.",
    icon: "calendar",
  },
  {
    chave: "financeiro",
    titulo: "Financeiro",
    descricao: "Pagamentos pendentes, recebimentos e ajustes importantes.",
    icon: "finance",
  },
  {
    chave: "conversas",
    titulo: "Conversas",
    descricao: "Clientes aguardando, transferências e novas mensagens.",
    icon: "chat",
  },
  {
    chave: "avaliacoes",
    titulo: "Avaliações",
    descricao: "Novas avaliações e alertas de notas baixas.",
    icon: "check",
  },
  {
    chave: "integracoes",
    titulo: "Integrações",
    descricao: "Falhas ou desconexões do WhatsApp e outros canais.",
    icon: "settings",
  },
  {
    chave: "planos_limites",
    titulo: "Plano e limites",
    descricao: "Consumo próximo do limite, teste e assinatura.",
    icon: "lock",
  },
  {
    chave: "sistema",
    titulo: "Sistema",
    descricao: "Avisos gerais de segurança e operação.",
    icon: "bell",
  },
];

export function Notificacoes() {
  const [notificacoes, setNotificacoes] = useState<Notificacao[]>([]);
  const [preferencias, setPreferencias] = useState<Preferencias | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");

  const todasDesativadas = preferencias
    ? opcoes.every((item) => !preferencias[item.chave])
    : true;

  async function carregar() {
    setCarregando(true);
    setErro("");
    try {
      const [dadosNotificacoes, dadosPreferencias] = await Promise.all([
        apiRequest<Notificacao[]>("/notificacoes"),
        apiRequest<Preferencias>("/preferencias-notificacoes"),
      ]);
      setNotificacoes(dadosNotificacoes);
      setPreferencias(dadosPreferencias);
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível carregar as notificações.",
      );
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    void carregar();
  }, []);

  useEffect(() => {
    if (!sucesso) return;
    const timer = window.setTimeout(() => setSucesso(""), 4000);
    return () => window.clearTimeout(timer);
  }, [sucesso]);

  async function marcarLida(item: Notificacao) {
    try {
      const atualizada = await apiRequest<Notificacao>(
        `/notificacoes/${item.id}/lida`,
        { method: "PATCH" },
      );
      setNotificacoes((atuais) =>
        atuais.map((notificacao) =>
          notificacao.id === atualizada.id ? atualizada : notificacao,
        ),
      );
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível marcar a notificação.",
      );
    }
  }

  async function marcarTodas() {
    try {
      await apiRequest<{ mensagem: string }>("/notificacoes/marcar-todas-lidas", {
        method: "PATCH",
      });
      setNotificacoes((atuais) =>
        atuais.map((item) => ({ ...item, lida: true })),
      );
      setSucesso("Todas as notificações foram marcadas como lidas.");
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível atualizar as notificações.",
      );
    }
  }

  async function atualizarPreferencias(payload: Record<ChavePreferencia, boolean>) {
    return apiRequest<Preferencias>("/preferencias-notificacoes", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  }

  async function desativarTodas() {
    if (!preferencias || todasDesativadas) return;

    setSalvando(true);
    setErro("");
    try {
      const payload = Object.fromEntries(
        opcoes.map((item) => [item.chave, false]),
      ) as Record<ChavePreferencia, boolean>;
      setPreferencias(await atualizarPreferencias(payload));
      setSucesso("Todas as categorias de notificação foram desativadas.");
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível desativar as notificações.",
      );
    } finally {
      setSalvando(false);
    }
  }

  async function salvarPreferencias(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!preferencias) return;
    setSalvando(true);
    setErro("");
    try {
      const payload = Object.fromEntries(
        opcoes.map((item) => [item.chave, preferencias[item.chave]]),
      ) as Record<ChavePreferencia, boolean>;
      setPreferencias(await atualizarPreferencias(payload));
      setSucesso("Preferências salvas com sucesso.");
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível salvar as preferências.",
      );
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Central de atenção"
        title="Notificações"
        description="Acompanhe avisos importantes e escolha quais categorias deseja receber."
        actions={
          <button
            className="button button-secondary"
            type="button"
            onClick={() => void marcarTodas()}
            disabled={!notificacoes.some((item) => !item.lida)}
          >
            <Icon name="check" size={17} />
            Marcar todas como lidas
          </button>
        }
      />

      {erro && <Alert>{erro}</Alert>}
      {sucesso && <Alert type="success">{sucesso}</Alert>}

      {carregando ? (
        <LoadingState label="Carregando notificações..." />
      ) : (
        <div className="notifications-page-grid">
          <section className="content-card">
            <div className="card-heading">
              <div>
                <span>Histórico</span>
                <h2>Avisos recentes</h2>
              </div>
              <strong className="number-pill">
                {notificacoes.filter((item) => !item.lida).length}
              </strong>
            </div>

            {notificacoes.length === 0 ? (
              <EmptyState
                icon="bell"
                title="Nenhuma notificação"
                description="Tudo certo por aqui. Novos avisos aparecerão nesta central."
              />
            ) : (
              <div className="notification-list notification-page-list">
                {notificacoes.map((item) => (
                  <article
                    className={`notification-item ${item.lida ? "notification-read" : ""}`}
                    key={item.id}
                  >
                    <span className="notification-icon">
                      <Icon name="bell" size={18} />
                    </span>
                    <div>
                      <strong>{item.titulo}</strong>
                      <p>{item.mensagem}</p>
                      <small>{formatDateTime(item.created_at)}</small>
                    </div>
                    {!item.lida && (
                      <button
                        className="button button-small button-secondary"
                        type="button"
                        onClick={() => void marcarLida(item)}
                      >
                        Marcar como lida
                      </button>
                    )}
                  </article>
                ))}
              </div>
            )}
          </section>

          <aside className="content-card notification-preferences-card">
            <div className="card-heading notification-preferences-heading">
              <div>
                <span>Preferências pessoais</span>
                <h2>O que deseja receber</h2>
              </div>
              <button
                className="button button-small button-secondary notification-disable-all"
                type="button"
                onClick={() => void desativarTodas()}
                disabled={salvando || todasDesativadas}
              >
                <Icon name="bell" size={15} />
                {todasDesativadas ? "Tudo desativado" : "Desativar todas"}
              </button>
            </div>
            {preferencias && (
              <form onSubmit={salvarPreferencias}>
                <div className="notification-preference-list">
                  {opcoes.map((item) => (
                    <label key={item.chave}>
                      <span className="notification-preference-icon">
                        <Icon name={item.icon} size={17} />
                      </span>
                      <span>
                        <strong>{item.titulo}</strong>
                        <small>{item.descricao}</small>
                      </span>
                      <span className="switch-control">
                        <input
                          type="checkbox"
                          checked={preferencias[item.chave]}
                          disabled={salvando}
                          onChange={(event) =>
                            setPreferencias({
                              ...preferencias,
                              [item.chave]: event.target.checked,
                            })
                          }
                        />
                        <span className="switch-slider" />
                      </span>
                    </label>
                  ))}
                </div>
                <div className="form-footer">
                  <button
                    className="button button-primary"
                    type="submit"
                    disabled={salvando}
                  >
                    {salvando ? "Salvando..." : "Salvar preferências"}
                  </button>
                </div>
              </form>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}
