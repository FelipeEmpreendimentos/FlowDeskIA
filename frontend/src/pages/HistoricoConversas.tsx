import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { Icon } from "../components/Icon";
import { Modal } from "../components/Modal";
import {
  Alert,
  EmptyState,
  LoadingState,
  PageHeader,
  StatusBadge,
} from "../components/UI";
import { apiRequest, buildQuery } from "../services/api";
import { showAppToast } from "../services/feedback";
import type { Cliente, Conversa, Mensagem, Usuario } from "../types";
import { formatDateTime } from "../utils/format";

type FiltroAvaliacao = "TODAS" | "RESPONDIDA" | "PENDENTE" | "SEM_AVALIACAO";

export function HistoricoConversas() {
  const navigate = useNavigate();
  const [conversas, setConversas] = useState<Conversa[]>([]);
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [mensagens, setMensagens] = useState<Mensagem[]>([]);
  const [selecionada, setSelecionada] = useState<Conversa | null>(null);
  const [busca, setBusca] = useState("");
  const [filtroAvaliacao, setFiltroAvaliacao] =
    useState<FiltroAvaliacao>("TODAS");
  const [carregando, setCarregando] = useState(true);
  const [carregandoMensagens, setCarregandoMensagens] = useState(false);
  const [modalReabertura, setModalReabertura] = useState(false);
  const [processando, setProcessando] = useState(false);
  const [erro, setErro] = useState("");

  async function carregarConversas(preservarId?: number) {
    setCarregando(true);
    setErro("");
    try {
      const [dadosConversas, dadosClientes, dadosUsuarios] = await Promise.all([
        apiRequest<Conversa[]>(
          `/conversas${buildQuery({ grupo: "HISTORICO", limit: 100 })}`,
        ),
        apiRequest<Cliente[]>("/clientes?limit=100"),
        apiRequest<Usuario[]>("/conversas/responsaveis?limit=100"),
      ]);
      setConversas(dadosConversas);
      setClientes(dadosClientes);
      setUsuarios(dadosUsuarios);
      setSelecionada(
        dadosConversas.find((item) => item.id === preservarId) ??
          dadosConversas[0] ??
          null,
      );
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível carregar o histórico.",
      );
    } finally {
      setCarregando(false);
    }
  }

  async function carregarMensagens(conversa: Conversa) {
    setCarregandoMensagens(true);
    setErro("");
    try {
      setMensagens(
        await apiRequest<Mensagem[]>(
          `/conversas/${conversa.id}/mensagens?limit=300`,
        ),
      );
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível carregar as mensagens.",
      );
    } finally {
      setCarregandoMensagens(false);
    }
  }

  useEffect(() => {
    void carregarConversas();
  }, []);

  useEffect(() => {
    if (selecionada) void carregarMensagens(selecionada);
    else setMensagens([]);
  }, [selecionada?.id]);

  const filtradas = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    return conversas.filter((conversa) => {
      const cliente = clientes.find((item) => item.id === conversa.cliente_id);
      const responsavel = usuarios.find(
        (item) => item.id === conversa.responsavel_id,
      );
      const correspondeBusca =
        !termo ||
        cliente?.nome.toLowerCase().includes(termo) ||
        cliente?.whatsapp?.toLowerCase().includes(termo) ||
        responsavel?.nome.toLowerCase().includes(termo) ||
        String(conversa.id).includes(termo);
      if (!correspondeBusca) return false;
      if (filtroAvaliacao === "RESPONDIDA") {
        return conversa.avaliacao_nota !== null;
      }
      if (filtroAvaliacao === "PENDENTE") {
        return conversa.avaliacao_solicitada && conversa.avaliacao_nota === null;
      }
      if (filtroAvaliacao === "SEM_AVALIACAO") {
        return !conversa.avaliacao_solicitada;
      }
      return true;
    });
  }, [busca, clientes, conversas, filtroAvaliacao, usuarios]);

  useEffect(() => {
    if (carregando) return;
    const proxima =
      filtradas.find((item) => item.id === selecionada?.id) ??
      filtradas[0] ??
      null;
    if (proxima?.id !== selecionada?.id) setSelecionada(proxima);
  }, [carregando, filtradas, selecionada?.id]);

  const clienteNome = (id: number) =>
    clientes.find((item) => item.id === id)?.nome ?? `Cliente #${id}`;

  const usuarioNome = (id: number | null) =>
    id
      ? usuarios.find((item) => item.id === id)?.nome ?? `Usuário #${id}`
      : "Sem responsável";

  function avaliacaoTexto(conversa: Conversa): string {
    if (conversa.avaliacao_nota !== null) {
      return `${conversa.avaliacao_nota} de 5 estrelas`;
    }
    if (conversa.avaliacao_solicitada) {
      return conversa.avaliacao_enviada_em
        ? "Aguardando resposta"
        : "Pendente de envio";
    }
    return "Sem avaliação";
  }

  async function reabrirConversa() {
    if (!selecionada) return;
    setProcessando(true);
    setErro("");
    try {
      await apiRequest<Conversa>(`/conversas/${selecionada.id}/reabrir`, {
        method: "POST",
      });
      setModalReabertura(false);
      showAppToast("Conversa reaberta e colocada em atendimento.");
      navigate("/conversas");
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível reabrir a conversa.",
      );
    } finally {
      setProcessando(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Atendimento"
        title="Histórico"
        description="Consulte conversas finalizadas, avaliações e resumos dos atendimentos."
      />

      {erro && !modalReabertura && <Alert>{erro}</Alert>}

      <section className="conversation-shell">
        <aside className="conversation-list-panel">
          <div className="conversation-filters">
            <label className="search-field">
              <Icon name="search" size={17} />
              <input
                value={busca}
                onChange={(event) => setBusca(event.target.value)}
                placeholder="Buscar cliente ou responsável"
              />
            </label>
            <select
              value={filtroAvaliacao}
              onChange={(event) =>
                setFiltroAvaliacao(event.target.value as FiltroAvaliacao)
              }
            >
              <option value="TODAS">Todas as finalizadas</option>
              <option value="RESPONDIDA">Com avaliação</option>
              <option value="PENDENTE">Avaliação pendente</option>
              <option value="SEM_AVALIACAO">Sem avaliação</option>
            </select>
          </div>

          {carregando ? (
            <LoadingState label="Carregando histórico..." />
          ) : filtradas.length === 0 ? (
            <EmptyState
              icon="clock"
              title="Nenhuma conversa no histórico"
              description="Conversas finalizadas serão organizadas nesta área."
            />
          ) : (
            <div className="conversation-list">
              {filtradas.map((item) => (
                <button
                  className={`conversation-list-item ${
                    selecionada?.id === item.id
                      ? "conversation-list-item-active"
                      : ""
                  }`}
                  type="button"
                  key={item.id}
                  onClick={() => setSelecionada(item)}
                >
                  <span className="entity-avatar">
                    {clienteNome(item.cliente_id).charAt(0).toUpperCase()}
                  </span>
                  <div>
                    <strong>{clienteNome(item.cliente_id)}</strong>
                    <small>
                      {item.finalizada_em
                        ? `Finalizada em ${formatDateTime(item.finalizada_em)}`
                        : "Finalização sem data informada"}
                    </small>
                  </div>
                  <div className="conversation-list-signals">
                    <StatusBadge value={item.status} />
                  </div>
                </button>
              ))}
            </div>
          )}
        </aside>

        <section className="chat-panel chat-panel-finalized">
          {!selecionada ? (
            <EmptyState
              icon="clock"
              title="Selecione uma conversa"
              description="Escolha um atendimento finalizado na lista ao lado."
            />
          ) : (
            <>
              <header className="chat-header">
                <div className="entity-cell">
                  <span className="entity-avatar">
                    {clienteNome(selecionada.cliente_id)
                      .charAt(0)
                      .toUpperCase()}
                  </span>
                  <div>
                    <strong>{clienteNome(selecionada.cliente_id)}</strong>
                    <small>
                      {selecionada.origem} · {usuarioNome(selecionada.responsavel_id)}
                    </small>
                  </div>
                </div>
                <div className="chat-history-controls">
                  <span className="conversation-evaluation-chip">
                    <Icon name="check" size={15} />
                    {avaliacaoTexto(selecionada)}
                  </span>
                  <button
                    className="button button-secondary button-small"
                    type="button"
                    onClick={() => {
                      setErro("");
                      setModalReabertura(true);
                    }}
                  >
                    <Icon name="refresh" size={16} />
                    Reabrir conversa
                  </button>
                </div>
              </header>

              <div className="conversation-finalization-summary">
                <div>
                  <span>Finalizada</span>
                  <strong>
                    {selecionada.finalizada_em
                      ? formatDateTime(selecionada.finalizada_em)
                      : "Data não informada"}
                  </strong>
                </div>
                <div>
                  <span>Responsável</span>
                  <strong>{usuarioNome(selecionada.finalizada_por_id)}</strong>
                </div>
                <div>
                  <span>Avaliação</span>
                  <strong>{avaliacaoTexto(selecionada)}</strong>
                </div>
                {selecionada.resumo_finalizacao && (
                  <div className="conversation-finalization-note">
                    <span>Resumo</span>
                    <p>{selecionada.resumo_finalizacao}</p>
                  </div>
                )}
              </div>

              <div className="messages-area">
                {carregandoMensagens ? (
                  <LoadingState label="Carregando mensagens..." />
                ) : mensagens.length === 0 ? (
                  <div className="compact-empty">
                    Nenhuma mensagem enviada nessa conversa.
                  </div>
                ) : (
                  mensagens.map((item) => (
                    <div
                      className={`message-row ${
                        item.remetente === "CLIENTE"
                          ? "message-in"
                          : "message-out"
                      }`}
                      key={item.id}
                    >
                      <div className="message-bubble">
                        <span>{item.remetente}</span>
                        <p>{item.conteudo}</p>
                        <small>{formatDateTime(item.data_envio)}</small>
                      </div>
                    </div>
                  ))
                )}
              </div>

              <div className="conversation-readonly-footer">
                <Icon name="lock" size={16} />
                Esta conversa está finalizada e disponível somente para consulta.
              </div>
            </>
          )}
        </section>
      </section>

      <Modal
        open={modalReabertura}
        title="Reabrir conversa"
        subtitle="Confirme antes de retomar o atendimento."
        onClose={() => !processando && setModalReabertura(false)}
        size="small"
      >
        <div className="confirmation-dialog">
          <span className="confirmation-icon confirmation-icon-success">
            <Icon name="refresh" size={24} />
          </span>
          <div className="confirmation-copy">
            <strong>Reabrir esta conversa?</strong>
            <p>
              Ela voltará como Em atendimento, ficará sob sua responsabilidade
              e aparecerá novamente em Conversas.
            </p>
          </div>
          {erro && <Alert>{erro}</Alert>}
          <div className="modal-actions confirmation-actions">
            <button
              className="button button-secondary"
              type="button"
              onClick={() => setModalReabertura(false)}
              disabled={processando}
            >
              Cancelar
            </button>
            <button
              className="button button-primary"
              type="button"
              onClick={() => void reabrirConversa()}
              disabled={processando}
            >
              {processando ? "Reabrindo..." : "Reabrir conversa"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
