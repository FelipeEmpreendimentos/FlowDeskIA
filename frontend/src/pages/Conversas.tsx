import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useOutletContext } from "react-router";
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
import type {
  AppOutletContext,
  Cliente,
  Conversa,
  Mensagem,
  OrigemConversa,
  StatusConversa,
  Usuario,
} from "../types";
import { formatDateTime } from "../utils/format";

type VisualizacaoConversa = "ATUAIS" | "HISTORICO";
type EscopoAtendimento = "MEUS" | "IA" | "GERAL";
type FiltroAvaliacao = "TODAS" | "RESPONDIDA" | "PENDENTE" | "SEM_AVALIACAO";

interface NovaConversaForm {
  cliente_id: string;
  responsavel_id: string;
  origem: OrigemConversa;
}

interface FinalizacaoForm {
  resumo_finalizacao: string;
  enviar_avaliacao: boolean;
}

const novaConversaVazia: NovaConversaForm = {
  cliente_id: "",
  responsavel_id: "",
  origem: "WHATSAPP",
};

const finalizacaoVazia: FinalizacaoForm = {
  resumo_finalizacao: "",
  enviar_avaliacao: true,
};

export function Conversas() {
  const { usuario } = useOutletContext<AppOutletContext>();
  const [conversas, setConversas] = useState<Conversa[]>([]);
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [mensagens, setMensagens] = useState<Mensagem[]>([]);
  const [selecionada, setSelecionada] = useState<Conversa | null>(null);
  const [visualizacao, setVisualizacao] =
    useState<VisualizacaoConversa>("ATUAIS");
  const [escopoAtendimento, setEscopoAtendimento] =
    useState<EscopoAtendimento>("MEUS");
  const [filtroStatus, setFiltroStatus] = useState("");
  const [filtroAvaliacao, setFiltroAvaliacao] =
    useState<FiltroAvaliacao>("TODAS");
  const [busca, setBusca] = useState("");
  const [texto, setTexto] = useState("");
  const [carregando, setCarregando] = useState(true);
  const [carregandoMensagens, setCarregandoMensagens] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [assumindoConversa, setAssumindoConversa] = useState(false);
  const [modalAberto, setModalAberto] = useState(false);
  const [modalFinalizacao, setModalFinalizacao] = useState(false);
  const [modalReabertura, setModalReabertura] = useState(false);
  const [processandoStatus, setProcessandoStatus] = useState(false);
  const [novaConversa, setNovaConversa] =
    useState<NovaConversaForm>(novaConversaVazia);
  const [finalizacao, setFinalizacao] =
    useState<FinalizacaoForm>(finalizacaoVazia);
  const [conversaExistenteId, setConversaExistenteId] = useState<number | null>(null);
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");

  async function carregarConversas(
    preservarId?: number,
    grupo: VisualizacaoConversa = visualizacao,
  ) {
    setCarregando(true);
    setErro("");

    try {
      const [dadosConversas, dadosClientes, dadosUsuarios] = await Promise.all([
        apiRequest<Conversa[]>(
          `/conversas${buildQuery({
            grupo,
            status_conversa: grupo === "ATUAIS" ? filtroStatus : undefined,
            limit: 100,
          })}`,
        ),
        apiRequest<Cliente[]>("/clientes?limit=100"),
        apiRequest<Usuario[]>("/conversas/responsaveis?limit=100"),
      ]);

      setConversas(dadosConversas);
      setClientes(dadosClientes);
      setUsuarios(dadosUsuarios);

      const id = preservarId ?? selecionada?.id;
      const proxima =
        dadosConversas.find((item) => item.id === id) ??
        dadosConversas[0] ??
        null;
      setSelecionada(proxima);
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível carregar as conversas.",
      );
    } finally {
      setCarregando(false);
    }
  }

  async function carregarMensagens(conversa: Conversa) {
    setCarregandoMensagens(true);
    setErro("");

    try {
      const data = await apiRequest<Mensagem[]>(
        `/conversas/${conversa.id}/mensagens?limit=300`,
      );
      setMensagens(data);

      const naoLidas = data.filter(
        (item) => item.remetente === "CLIENTE" && !item.lida,
      );

      if (naoLidas.length > 0) {
        await Promise.all(
          naoLidas.map((item) =>
            apiRequest<Mensagem>(
              `/conversas/${conversa.id}/mensagens/${item.id}/lida`,
              { method: "PATCH" },
            ),
          ),
        );
        setMensagens((atuais) =>
          atuais.map((item) =>
            naoLidas.some((naoLida) => naoLida.id === item.id)
              ? { ...item, lida: true }
              : item,
          ),
        );
      }
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
    void carregarConversas(undefined, visualizacao);
  }, [filtroStatus, visualizacao]);

  useEffect(() => {
    if (selecionada) {
      void carregarMensagens(selecionada);
    } else {
      setMensagens([]);
    }
  }, [selecionada?.id]);

  useEffect(() => {
    if (!sucesso) return;
    const timer = window.setTimeout(() => setSucesso(""), 4000);
    return () => window.clearTimeout(timer);
  }, [sucesso]);

  const totaisAtendimento = useMemo(
    () => ({
      MEUS: conversas.filter((item) => item.responsavel_id === usuario.id).length,
      IA: conversas.filter((item) => item.ia_ativa).length,
      GERAL: conversas.length,
    }),
    [conversas, usuario.id],
  );

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

      if (visualizacao === "ATUAIS") {
        if (escopoAtendimento === "MEUS") {
          return conversa.responsavel_id === usuario.id;
        }
        if (escopoAtendimento === "IA") {
          return conversa.ia_ativa;
        }
        return true;
      }

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
  }, [
    busca,
    clientes,
    conversas,
    escopoAtendimento,
    filtroAvaliacao,
    usuario.id,
    usuarios,
    visualizacao,
  ]);

  useEffect(() => {
    if (carregando) return;
    const proxima =
      filtradas.find((item) => item.id === selecionada?.id) ??
      filtradas[0] ??
      null;
    if (proxima?.id !== selecionada?.id) {
      setSelecionada(proxima);
    }
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

  async function criarConversa(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro("");
    setConversaExistenteId(null);

    try {
      const criada = await apiRequest<Conversa>("/conversas", {
        method: "POST",
        body: JSON.stringify({
          cliente_id: Number(novaConversa.cliente_id),
          responsavel_id: novaConversa.responsavel_id
            ? Number(novaConversa.responsavel_id)
            : null,
          origem: novaConversa.origem,
        }),
      });

      setModalAberto(false);
      setNovaConversa(novaConversaVazia);
      setSucesso("Conversa criada com sucesso.");
      setVisualizacao("ATUAIS");
      setEscopoAtendimento(
        criada.responsavel_id === usuario.id
          ? "MEUS"
          : criada.ia_ativa
            ? "IA"
            : "GERAL",
      );
      await carregarConversas(criada.id, "ATUAIS");
    } catch (error) {
      const mensagem =
        error instanceof Error
          ? error.message
          : "Não foi possível criar a conversa.";
      const match = mensagem.match(/conversa\s+#(\d+)/i);

      if (match) {
        showAppToast(
          "Este cliente já possui uma conversa ativa. Abrindo o atendimento existente.",
          { type: "warning" },
        );
        await abrirConversaExistente(Number(match[1]));
        return;
      }

      setErro(mensagem);
    }
  }

  async function abrirConversaExistente(idRecebido?: number) {
    const id = idRecebido ?? conversaExistenteId;
    if (!id) return;
    setModalAberto(false);
    setConversaExistenteId(null);
    setErro("");
    setVisualizacao("ATUAIS");
    setFiltroStatus("");
    setEscopoAtendimento("GERAL");
    await carregarConversas(id, "ATUAIS");
  }

  async function enviarMensagem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selecionada || !texto.trim() || selecionada.status === "FINALIZADA") {
      return;
    }

    setEnviando(true);
    setErro("");

    try {
      await apiRequest<Mensagem>(`/conversas/${selecionada.id}/mensagens`, {
        method: "POST",
        body: JSON.stringify({
          remetente: "FUNCIONARIO",
          conteudo: texto.trim(),
          tipo: "TEXTO",
          arquivo_url: null,
          id_whatsapp: null,
        }),
      });
      setTexto("");
      await carregarMensagens(selecionada);
      await carregarConversas(selecionada.id, "ATUAIS");
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível enviar a mensagem.",
      );
    } finally {
      setEnviando(false);
    }
  }

  async function atualizarConversa(values: {
    status?: StatusConversa;
    ia_ativa?: boolean;
    responsavel_id?: number | null;
  }) {
    if (!selecionada) return;
    setErro("");

    try {
      const atualizada = await apiRequest<Conversa>(
        `/conversas/${selecionada.id}`,
        {
          method: "PATCH",
          body: JSON.stringify(values),
        },
      );
      setSelecionada(atualizada);
      setSucesso("Conversa atualizada com sucesso.");
      if (atualizada.responsavel_id === usuario.id) {
        setEscopoAtendimento("MEUS");
      } else if (atualizada.ia_ativa) {
        setEscopoAtendimento("IA");
      }
      await carregarConversas(atualizada.id, "ATUAIS");
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível atualizar a conversa.",
      );
    }
  }

  async function assumirConversa() {
    if (!selecionada || selecionada.responsavel_id !== null) return;

    setAssumindoConversa(true);
    setErro("");
    try {
      const atualizada = await apiRequest<Conversa>(
        `/conversas/${selecionada.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({ responsavel_id: usuario.id }),
        },
      );
      setSelecionada(atualizada);
      setEscopoAtendimento("MEUS");
      setSucesso("Conversa assumida com sucesso.");
      await carregarConversas(atualizada.id, "ATUAIS");
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível assumir a conversa.",
      );
    } finally {
      setAssumindoConversa(false);
    }
  }

  function escolherAcaoStatus(value: string) {
    if (!selecionada || !value || value === selecionada.status) return;

    if (value === "FINALIZADA") {
      setFinalizacao(finalizacaoVazia);
      setErro("");
      setModalFinalizacao(true);
      return;
    }

    void atualizarConversa({ status: value as StatusConversa });
  }

  async function finalizarConversa(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selecionada) return;

    setProcessandoStatus(true);
    setErro("");

    try {
      const finalizada = await apiRequest<Conversa>(
        `/conversas/${selecionada.id}/finalizar`,
        {
          method: "POST",
          body: JSON.stringify(finalizacao),
        },
      );

      setModalFinalizacao(false);
      setFinalizacao(finalizacaoVazia);
      setSucesso(
        finalizada.avaliacao_solicitada
          ? "Conversa finalizada. A avaliação ficou preparada para envio."
          : "Conversa finalizada com sucesso.",
      );
      setVisualizacao("ATUAIS");
      await carregarConversas(undefined, "ATUAIS");
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível finalizar a conversa.",
      );
    } finally {
      setProcessandoStatus(false);
    }
  }

  async function reabrirConversa() {
    if (!selecionada) return;

    setProcessandoStatus(true);
    setErro("");

    try {
      const reaberta = await apiRequest<Conversa>(
        `/conversas/${selecionada.id}/reabrir`,
        { method: "POST" },
      );
      setModalReabertura(false);
      setSucesso("Conversa reaberta e colocada em atendimento.");
      setVisualizacao("ATUAIS");
      setEscopoAtendimento("MEUS");
      setFiltroStatus("EM_ATENDIMENTO");
      await carregarConversas(reaberta.id, "ATUAIS");
    } catch (error) {
      const mensagem =
        error instanceof Error
          ? error.message
          : "Não foi possível reabrir a conversa.";
      const match = mensagem.match(/conversa\s+#(\d+)/i);

      if (match) {
        const existenteId = Number(match[1]);
        setModalReabertura(false);
        setErro("");
        setVisualizacao("ATUAIS");
        setFiltroStatus("");
        setEscopoAtendimento("GERAL");
        showAppToast(
          "Este cliente já possui uma conversa ativa. Abrindo o atendimento existente.",
          { type: "warning" },
        );
        await carregarConversas(existenteId, "ATUAIS");
        return;
      }

      setErro(mensagem);
    } finally {
      setProcessandoStatus(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Atendimento"
        title="Conversas"
        description="Centralize mensagens e acompanhe o atendimento de cada cliente."
        actions={
          <button
            className="button button-primary"
            type="button"
            onClick={() => {
              setNovaConversa(novaConversaVazia);
              setConversaExistenteId(null);
              setErro("");
              setModalAberto(true);
            }}
          >
            <Icon name="plus" size={18} />
            Nova conversa
          </button>
        }
      />

      {sucesso && (
        <div className="app-toast-region" aria-live="polite" aria-atomic="true">
          <div className="app-toast app-toast-success" role="status">
            <span className="app-toast-icon">
              <Icon name="check" size={18} />
            </span>
            <div className="app-toast-copy">
              <strong>Sucesso</strong>
              <span>{sucesso}</span>
            </div>
            <button
              className="app-toast-close"
              type="button"
              onClick={() => setSucesso("")}
              aria-label="Fechar notificação"
            >
              <Icon name="close" size={17} />
            </button>
          </div>
        </div>
      )}

      {erro &&
        !modalAberto &&
        !modalFinalizacao &&
        !modalReabertura && <Alert>{erro}</Alert>}

      <div className="conversation-view-tabs" role="tablist">
        <button
          className={visualizacao === "ATUAIS" ? "conversation-view-tab-active" : ""}
          type="button"
          onClick={() => {
            setVisualizacao("ATUAIS");
            setFiltroAvaliacao("TODAS");
          }}
        >
          <Icon name="chat" size={17} />
          Atendimentos
        </button>
        <button
          className={visualizacao === "HISTORICO" ? "conversation-view-tab-active" : ""}
          type="button"
          onClick={() => {
            setVisualizacao("HISTORICO");
            setFiltroStatus("");
          }}
        >
          <Icon name="clock" size={17} />
          Histórico
        </button>
      </div>

      {visualizacao === "ATUAIS" && (
        <div className="conversation-scope-switch" aria-label="Tipo de atendimento">
          {(
            [
              ["MEUS", "Meus", "team"],
              ["IA", "IA", "bot"],
              ["GERAL", "Geral", "chat"],
            ] as const
          ).map(([value, label, icon]) => (
            <button
              className={escopoAtendimento === value ? "active" : ""}
              type="button"
              key={value}
              onClick={() => setEscopoAtendimento(value)}
              aria-pressed={escopoAtendimento === value}
            >
              <Icon name={icon} size={16} />
              <span>{label}</span>
              <strong>{totaisAtendimento[value]}</strong>
            </button>
          ))}
        </div>
      )}

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

            {visualizacao === "ATUAIS" ? (
              <select
                value={filtroStatus}
                onChange={(event) => setFiltroStatus(event.target.value)}
              >
                <option value="">Todas as atuais</option>
                <option value="ABERTA">Abertas</option>
                <option value="EM_ATENDIMENTO">Em atendimento</option>
              </select>
            ) : (
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
            )}
          </div>

          {carregando ? (
            <LoadingState label="Carregando..." />
          ) : filtradas.length === 0 ? (
            <EmptyState
              icon={visualizacao === "ATUAIS" ? "chat" : "clock"}
              title={
                visualizacao === "ATUAIS"
                  ? "Nenhuma conversa neste grupo"
                  : "Nenhuma conversa no histórico"
              }
              description={
                visualizacao === "ATUAIS"
                  ? "Troque entre Meus, IA e Geral ou ajuste os filtros."
                  : "Conversas finalizadas serão organizadas nesta aba."
              }
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
                      {item.status === "FINALIZADA" && item.finalizada_em
                        ? `Finalizada em ${formatDateTime(item.finalizada_em)}`
                        : item.ultima_interacao
                          ? formatDateTime(item.ultima_interacao)
                          : "Sem mensagens"}
                    </small>
                  </div>
                  <div className="conversation-list-signals">
                    <span
                      className={`conversation-ai-icon ${
                        item.ia_ativa
                          ? "conversation-ai-icon-active"
                          : "conversation-ai-icon-paused"
                      }`}
                      title={item.ia_ativa ? "IA ativa" : "IA pausada"}
                    >
                      <Icon name="bot" size={14} />
                    </span>
                    <StatusBadge value={item.status} />
                  </div>
                </button>
              ))}
            </div>
          )}
        </aside>

        <section
          className={`chat-panel ${selecionada?.status === "FINALIZADA" ? "chat-panel-finalized" : ""}`}
        >
          {!selecionada ? (
            <EmptyState
              icon="chat"
              title="Selecione uma conversa"
              description="Escolha um atendimento na lista ao lado."
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
                    {selecionada.status !== "FINALIZADA" &&
                      selecionada.responsavel_id === null && (
                        <button
                          className="button button-secondary button-small conversation-assume-button"
                          type="button"
                          onClick={() => void assumirConversa()}
                          disabled={assumindoConversa}
                        >
                          <Icon name="team" size={15} />
                          {assumindoConversa ? "Assumindo..." : "Assumir conversa"}
                        </button>
                      )}
                  </div>
                </div>

                {selecionada.status === "FINALIZADA" ? (
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
                ) : (
                  <div className="chat-controls">
                    <select
                      value={selecionada.responsavel_id ?? ""}
                      onChange={(event) =>
                        void atualizarConversa({
                          responsavel_id: event.target.value
                            ? Number(event.target.value)
                            : null,
                        })
                      }
                      title="Responsável"
                    >
                      <option value="">Sem responsável</option>
                      {usuarios
                        .filter(
                          (item) =>
                            item.ativo ||
                            item.id === selecionada.responsavel_id,
                        )
                        .map((item) => (
                          <option key={item.id} value={item.id}>
                            {item.nome}
                          </option>
                        ))}
                    </select>

                    <select
                      value={selecionada.status}
                      onChange={(event) => escolherAcaoStatus(event.target.value)}
                      title="Status da conversa"
                    >
                      <option value="ABERTA">Aberta</option>
                      <option value="EM_ATENDIMENTO">Em atendimento</option>
                      <option value="FINALIZADA">Finalizar conversa</option>
                    </select>

                    <button
                      className={`conversation-ai-control ${
                        selecionada.ia_ativa
                          ? "conversation-ai-control-active"
                          : "conversation-ai-control-paused"
                      }`}
                      type="button"
                      onClick={() =>
                        void atualizarConversa({
                          ia_ativa: !selecionada.ia_ativa,
                        })
                      }
                      title={
                        selecionada.ia_ativa
                          ? "A IA está ativa nesta conversa"
                          : "A IA está pausada nesta conversa"
                      }
                    >
                      <Icon name="bot" size={16} />
                      <span>
                        IA {selecionada.ia_ativa ? "ativa" : "pausada"}
                      </span>
                    </button>
                  </div>
                )}
              </header>

              {selecionada.status === "FINALIZADA" && (
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
              )}

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
                        <small>
                          {formatDateTime(item.data_envio)}
                          {item.remetente === "CLIENTE" && item.lida
                            ? " · Lida"
                            : ""}
                        </small>
                      </div>
                    </div>
                  ))
                )}
              </div>

              {selecionada.status !== "FINALIZADA" ? (
                <form className="message-form" onSubmit={enviarMensagem}>
                  <textarea
                    rows={1}
                    value={texto}
                    onChange={(event) => setTexto(event.target.value)}
                    placeholder="Digite uma mensagem..."
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && !event.shiftKey) {
                        event.preventDefault();
                        event.currentTarget.form?.requestSubmit();
                      }
                    }}
                  />
                  <button
                    className="send-button"
                    type="submit"
                    disabled={enviando || !texto.trim()}
                    aria-label="Enviar mensagem"
                  >
                    <Icon name="send" size={20} />
                  </button>
                </form>
              ) : (
                <div className="conversation-readonly-footer">
                  <Icon name="lock" size={16} />
                  Esta conversa está finalizada e disponível somente para consulta.
                </div>
              )}
            </>
          )}
        </section>
      </section>

      <Modal
        open={modalAberto}
        title="Nova conversa"
        subtitle="Escolha o cliente, a origem e o responsável inicial."
        onClose={() => {
          setModalAberto(false);
          setConversaExistenteId(null);
          setErro("");
        }}
      >
        <form onSubmit={criarConversa}>
          {erro && (
            conversaExistenteId ? (
              <Alert>
                <div className="conversation-existing-alert">
                  <span>{erro}</span>
                  <button
                    className="button button-secondary button-small"
                    type="button"
                    onClick={() => void abrirConversaExistente()}
                  >
                    <Icon name="chat" size={16} />
                    Abrir conversa existente
                  </button>
                </div>
              </Alert>
            ) : (
              <Alert>{erro}</Alert>
            )
          )}
          <div className="form-grid">
            <label className="field">
              Cliente
              <select
                value={novaConversa.cliente_id}
                onChange={(event) => {
                  setConversaExistenteId(null);
                  setErro("");
                  setNovaConversa({
                    ...novaConversa,
                    cliente_id: event.target.value,
                  });
                }}
                required
              >
                <option value="">Selecione</option>
                {clientes
                  .filter((item) => item.status === "ATIVO")
                  .map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.nome}
                    </option>
                  ))}
              </select>
            </label>
            <label className="field">
              Responsável
              <select
                value={novaConversa.responsavel_id}
                onChange={(event) =>
                  setNovaConversa({
                    ...novaConversa,
                    responsavel_id: event.target.value,
                  })
                }
              >
                <option value="">Atendimento inicial pela IA</option>
                {usuarios
                  .filter((item) => item.ativo)
                  .map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.nome}
                    </option>
                  ))}
              </select>
            </label>
            <label className="field">
              Origem
              <select
                value={novaConversa.origem}
                onChange={(event) => {
                  setConversaExistenteId(null);
                  setErro("");
                  setNovaConversa({
                    ...novaConversa,
                    origem: event.target.value as OrigemConversa,
                  });
                }}
              >
                <option value="WHATSAPP">WhatsApp</option>
                <option value="INSTAGRAM">Instagram</option>
                <option value="SITE">Site</option>
              </select>
            </label>
          </div>
          <div className="modal-actions">
            <button
              className="button button-secondary"
              type="button"
              onClick={() => {
                setModalAberto(false);
                setConversaExistenteId(null);
                setErro("");
              }}
            >
              Cancelar
            </button>
            <button className="button button-primary" type="submit">
              Criar conversa
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        open={modalFinalizacao}
        title="Finalizar conversa"
        subtitle="Confirme a finalização do atendimento."
        onClose={() => !processandoStatus && setModalFinalizacao(false)}
        size="small"
      >
        <form className="conversation-finish-form" onSubmit={finalizarConversa}>
          {erro && <Alert>{erro}</Alert>}

          <div className="confirmation-dialog">
            <span className="confirmation-icon confirmation-icon-success">
              <Icon name="check" size={24} />
            </span>
            <div className="confirmation-copy">
              <strong>Finalizar este atendimento?</strong>
              <p>
                A IA será pausada e a conversa será marcada como finalizada.
                Se necessário, ela poderá ser reaberta posteriormente.
              </p>
            </div>
          </div>

          <label className="field">
            Resumo do atendimento <small>(opcional)</small>
            <textarea
              rows={4}
              value={finalizacao.resumo_finalizacao}
              onChange={(event) =>
                setFinalizacao({
                  ...finalizacao,
                  resumo_finalizacao: event.target.value,
                })
              }
              placeholder="Ex.: Cliente orientado e lavagem agendada."
            />
          </label>

          <label className="conversation-evaluation-option">
            <input
              type="checkbox"
              checked={finalizacao.enviar_avaliacao}
              onChange={(event) =>
                setFinalizacao({
                  ...finalizacao,
                  enviar_avaliacao: event.target.checked,
                })
              }
            />
            <span>
              <strong>Enviar avaliação ao cliente</strong>
              <small>
                O pedido ficará registrado agora. O disparo automático pelo
                WhatsApp será realizado quando a integração do canal estiver
                conectada.
              </small>
            </span>
          </label>

          <div className="modal-actions">
            <button
              className="button button-secondary"
              type="button"
              onClick={() => setModalFinalizacao(false)}
              disabled={processandoStatus}
            >
              Cancelar
            </button>
            <button
              className="button button-primary"
              type="submit"
              disabled={processandoStatus}
            >
              {processandoStatus ? "Finalizando..." : "Finalizar conversa"}
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        open={modalReabertura}
        title="Reabrir conversa"
        subtitle="Confirme antes de retomar o atendimento."
        onClose={() => !processandoStatus && setModalReabertura(false)}
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
              e a IA permanecerá pausada.
            </p>
          </div>

          {erro && <Alert>{erro}</Alert>}

          <div className="modal-actions confirmation-actions">
            <button
              className="button button-secondary"
              type="button"
              onClick={() => setModalReabertura(false)}
              disabled={processandoStatus}
            >
              Cancelar
            </button>
            <button
              className="button button-primary"
              type="button"
              onClick={() => void reabrirConversa()}
              disabled={processandoStatus}
            >
              {processandoStatus ? "Reabrindo..." : "Reabrir conversa"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
