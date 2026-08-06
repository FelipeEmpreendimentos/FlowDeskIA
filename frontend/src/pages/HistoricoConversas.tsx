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
  const [modalVisualizacao, setModalVisualizacao] = useState(false);
  const [modalReabertura, setModalReabertura] = useState(false);
  const [processando, setProcessando] = useState(false);
  const [erro, setErro] = useState("");
  const [erroDetalhes, setErroDetalhes] = useState("");

  async function carregarConversas() {
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
    setErroDetalhes("");
    setMensagens([]);
    try {
      setMensagens(
        await apiRequest<Mensagem[]>(
          `/conversas/${conversa.id}/mensagens?limit=300`,
        ),
      );
    } catch (error) {
      setErroDetalhes(
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
        conversa.origem.toLowerCase().includes(termo) ||
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

  function abrirVisualizacao(conversa: Conversa) {
    setSelecionada(conversa);
    setModalVisualizacao(true);
    void carregarMensagens(conversa);
  }

  function fecharVisualizacao() {
    setModalVisualizacao(false);
    setErroDetalhes("");
    setMensagens([]);
  }

  function abrirConfirmacaoReabertura() {
    setModalVisualizacao(false);
    setModalReabertura(true);
    setErroDetalhes("");
  }

  function cancelarReabertura() {
    if (processando) return;
    setModalReabertura(false);
    setModalVisualizacao(true);
    setErroDetalhes("");
  }

  async function reabrirConversa() {
    if (!selecionada) return;
    setProcessando(true);
    setErroDetalhes("");
    try {
      await apiRequest<Conversa>(`/conversas/${selecionada.id}/reabrir`, {
        method: "POST",
      });
      setModalReabertura(false);
      showAppToast("Conversa reaberta e colocada em atendimento.");
      navigate("/conversas");
    } catch (error) {
      setErroDetalhes(
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

      {erro && <Alert>{erro}</Alert>}

      <section className="content-card conversation-history-card">
        <div className="conversation-history-toolbar">
          <label className="search-field conversation-history-search">
            <Icon name="search" size={18} />
            <input
              value={busca}
              onChange={(event) => setBusca(event.target.value)}
              placeholder="Buscar por cliente, responsável, origem ou número da conversa"
              aria-label="Buscar no histórico de conversas"
            />
          </label>

          <select
            value={filtroAvaliacao}
            onChange={(event) =>
              setFiltroAvaliacao(event.target.value as FiltroAvaliacao)
            }
            aria-label="Filtrar histórico por avaliação"
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
            description="Altere os filtros ou finalize uma conversa para consultá-la aqui."
          />
        ) : (
          <div className="table-wrap">
            <table className="data-table conversation-history-table">
              <thead>
                <tr>
                  <th>Cliente</th>
                  <th>Responsável</th>
                  <th>Finalização</th>
                  <th>Avaliação</th>
                  <th>Status</th>
                  <th className="actions-column">Ações</th>
                </tr>
              </thead>
              <tbody>
                {filtradas.map((conversa) => (
                  <tr key={conversa.id}>
                    <td>
                      <div className="entity-cell">
                        <span className="entity-avatar">
                          {clienteNome(conversa.cliente_id)
                            .charAt(0)
                            .toUpperCase()}
                        </span>
                        <div>
                          <strong>{clienteNome(conversa.cliente_id)}</strong>
                          <small>
                            Conversa #{conversa.id} · {conversa.origem}
                          </small>
                        </div>
                      </div>
                    </td>
                    <td>
                      <strong className="table-primary">
                        {usuarioNome(conversa.responsavel_id)}
                      </strong>
                      <small>Responsável pelo atendimento</small>
                    </td>
                    <td>
                      <strong className="table-primary">
                        {conversa.finalizada_em
                          ? formatDateTime(conversa.finalizada_em)
                          : "Data não informada"}
                      </strong>
                      <small>
                        {conversa.finalizada_por_id
                          ? `Por ${usuarioNome(conversa.finalizada_por_id)}`
                          : "Finalizador não informado"}
                      </small>
                    </td>
                    <td>{avaliacaoTexto(conversa)}</td>
                    <td>
                      <StatusBadge value={conversa.status} />
                    </td>
                    <td>
                      <div className="row-actions">
                        <button
                          className="icon-button"
                          type="button"
                          onClick={() => abrirVisualizacao(conversa)}
                          title="Visualizar conversa"
                          aria-label={`Visualizar conversa de ${clienteNome(
                            conversa.cliente_id,
                          )}`}
                        >
                          <Icon name="eye" size={18} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <Modal
        open={modalVisualizacao}
        title={
          selecionada
            ? `Conversa com ${clienteNome(selecionada.cliente_id)}`
            : "Visualizar conversa"
        }
        subtitle="Consulte o resumo e todas as mensagens deste atendimento finalizado."
        onClose={fecharVisualizacao}
        size="large"
      >
        {selecionada && (
          <div className="conversation-history-detail">
            {erroDetalhes && <Alert>{erroDetalhes}</Alert>}

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
              <div>
                <span>Origem</span>
                <strong>{selecionada.origem}</strong>
              </div>
              {selecionada.resumo_finalizacao && (
                <div className="conversation-finalization-note">
                  <span>Resumo</span>
                  <p>{selecionada.resumo_finalizacao}</p>
                </div>
              )}
            </div>

            <section className="conversation-history-messages">
              <div className="card-heading">
                <div>
                  <span>Conversa completa</span>
                  <h2>Mensagens do atendimento</h2>
                </div>
              </div>

              {carregandoMensagens ? (
                <LoadingState label="Carregando mensagens..." />
              ) : mensagens.length === 0 ? (
                <div className="compact-empty">
                  Nenhuma mensagem enviada nessa conversa.
                </div>
              ) : (
                <div className="conversation-history-message-list">
                  {mensagens.map((item) => (
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
                  ))}
                </div>
              )}
            </section>

            <div className="modal-actions">
              <button
                className="button button-secondary"
                type="button"
                onClick={fecharVisualizacao}
              >
                Fechar
              </button>
              <button
                className="button button-primary"
                type="button"
                onClick={abrirConfirmacaoReabertura}
              >
                <Icon name="refresh" size={16} />
                Reabrir conversa
              </button>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        open={modalReabertura}
        title="Reabrir conversa"
        subtitle="Confirme antes de retomar o atendimento."
        onClose={cancelarReabertura}
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
          {erroDetalhes && <Alert>{erroDetalhes}</Alert>}
          <div className="modal-actions confirmation-actions">
            <button
              className="button button-secondary"
              type="button"
              onClick={cancelarReabertura}
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
