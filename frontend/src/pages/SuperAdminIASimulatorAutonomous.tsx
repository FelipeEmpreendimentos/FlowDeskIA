import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Icon } from "../components/Icon";
import { superAdminApiRequest } from "../services/superAdminApi";
import type { EmpresaSuperAdminResumo } from "../types/superAdmin";
import "../whatsapp-simulator.css";
import "../ai-v2.css";
import "../guided-chat.css";
import "../guided-chat-autonomous.css";

type Speaker = "CLIENTE" | "IA";
type LabMode = "EXISTENTE" | "NOVO";

interface SimulatorClient {
  id: number;
  nome: string;
  whatsapp: string | null;
  telefone: string | null;
  status: string;
  criado_por_ia: boolean;
  cadastro_completo: boolean;
}

interface SimulatorVehicle {
  id: number;
  tipo_veiculo: string | null;
  marca: string | null;
  modelo: string | null;
  ano: number | null;
  cor: string | null;
  apelido: string | null;
}

interface SimulatorBootstrap {
  empresa_id: number;
  empresa: string;
  cliente_id: number;
  cliente: string;
  cliente_whatsapp: string | null;
  assistente: string;
  veiculos: SimulatorVehicle[];
  canal: string;
  novo_contato: boolean;
  criado_por_ia: boolean;
  cadastro_completo: boolean;
}

interface QuickReply {
  id: string;
  label: string;
  kind: string;
}

interface ChatMessage {
  id: string;
  remetente: Speaker;
  conteudo: string;
  createdAt: string;
  quickReplies?: QuickReply[];
}

interface ToolTrace {
  name: string;
  arguments: Record<string, unknown>;
  result: Record<string, unknown>;
}

interface SimulatorReply {
  id_whatsapp: string;
  remetente: "IA";
  conteudo: string;
  created_at: string;
  model: string;
  latency_ms: number;
  status: "ENTREGUE";
  intent: string | null;
  interpreted_as: string | null;
  agent_state: string;
  handoff: boolean;
  handoff_reason: string | null;
  customer_id: number | null;
  customer_complete: boolean;
  pending_action: Record<string, unknown> | null;
  quick_replies: QuickReply[];
  tools: ToolTrace[];
}

interface DebugState {
  intent: string | null;
  interpretedAs: string | null;
  agentState: string;
  handoff: boolean;
  handoffReason: string | null;
  customerComplete: boolean | null;
  pendingAction: Record<string, unknown> | null;
  tools: ToolTrace[];
}

const emptyDebug: DebugState = {
  intent: null,
  interpretedAs: null,
  agentState: "—",
  handoff: false,
  handoffReason: null,
  customerComplete: null,
  pendingAction: null,
  tools: [],
};

const scenarios = [
  { label: "Saudação", text: "Bom dia" },
  { label: "Erro no carro", text: "é um corola" },
  { label: "Texto → agendar", text: "Quero marcar um horário para lavar meu carro" },
  { label: "Texto → consultar", text: "Que horas está meu agendamento?" },
  { label: "Texto → cancelar", text: "Preciso cancelar meu horário" },
  { label: "Preço", text: "Quanto custa o serviço de vocês?" },
  { label: "Humano", text: "Quero falar com uma pessoa" },
  { label: "Fora do escopo", text: "Quero marcar uma tosa pro meu pug" },
  { label: "Confuso", text: "faz aquele trem lá meio depois talvez" },
];

function newId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function messageTime(value: string): string {
  return new Date(value).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function vehicleLabel(vehicle: SimulatorVehicle): string {
  const main = [vehicle.marca, vehicle.modelo].filter(Boolean).join(" ") || vehicle.apelido || "Veículo";
  return vehicle.cor ? `${main} · ${vehicle.cor}` : main;
}

function prettyJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export function SuperAdminIASimulatorAutonomous() {
  const endRef = useRef<HTMLDivElement | null>(null);
  const [empresas, setEmpresas] = useState<EmpresaSuperAdminResumo[]>([]);
  const [empresaId, setEmpresaId] = useState("");
  const [mode, setMode] = useState<LabMode>("EXISTENTE");
  const [clientes, setClientes] = useState<SimulatorClient[]>([]);
  const [clienteId, setClienteId] = useState("");
  const [busca, setBusca] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [bootstrap, setBootstrap] = useState<SimulatorBootstrap | null>(null);
  const [testContactCreated, setTestContactCreated] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState(newId);
  const [loadingCompanies, setLoadingCompanies] = useState(true);
  const [loadingClients, setLoadingClients] = useState(false);
  const [creatingContact, setCreatingContact] = useState(false);
  const [responding, setResponding] = useState(false);
  const [error, setError] = useState("");
  const [lastModel, setLastModel] = useState("—");
  const [lastLatency, setLastLatency] = useState<number | null>(null);
  const [debug, setDebug] = useState<DebugState>(emptyDebug);

  useEffect(() => {
    async function loadCompanies() {
      setLoadingCompanies(true);
      try {
        setEmpresas(await superAdminApiRequest<EmpresaSuperAdminResumo[]>("/empresas?limit=300"));
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Não foi possível carregar as empresas.");
      } finally {
        setLoadingCompanies(false);
      }
    }
    void loadCompanies();
  }, []);

  useEffect(() => {
    setClienteId("");
    setBootstrap(null);
    setMessages([]);
    setDebug(emptyDebug);
    setSessionId(newId());
    setTestContactCreated(false);
    if (!empresaId || mode !== "EXISTENTE") return;

    const timer = window.setTimeout(async () => {
      setLoadingClients(true);
      try {
        const query = new URLSearchParams({ limit: "250" });
        if (busca.trim()) query.set("busca", busca.trim());
        setClientes(
          await superAdminApiRequest<SimulatorClient[]>(
            `/simulador-ia/empresas/${empresaId}/clientes?${query.toString()}`,
          ),
        );
      } catch (requestError) {
        setClientes([]);
        setError(requestError instanceof Error ? requestError.message : "Não foi possível carregar clientes.");
      } finally {
        setLoadingClients(false);
      }
    }, 200);
    return () => window.clearTimeout(timer);
  }, [empresaId, busca, mode]);

  useEffect(() => {
    if (mode !== "EXISTENTE" || !empresaId || !clienteId) return;
    async function loadCustomer() {
      try {
        const data = await superAdminApiRequest<SimulatorBootstrap>(
          `/simulador-ia/empresas/${empresaId}/clientes/${clienteId}`,
        );
        setBootstrap(data);
        setSessionId(newId());
        setMessages([]);
        setDebug(emptyDebug);
        setLastModel("—");
        setLastLatency(null);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Não foi possível preparar o cliente.");
      }
    }
    void loadCustomer();
  }, [empresaId, clienteId, mode]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, responding]);

  const selectedCompany = useMemo(
    () => empresas.find((item) => String(item.id) === empresaId) ?? null,
    [empresas, empresaId],
  );

  async function refreshBootstrap(customerId = bootstrap?.cliente_id) {
    if (!empresaId || !customerId) return;
    try {
      setBootstrap(
        await superAdminApiRequest<SimulatorBootstrap>(
          `/simulador-ia/empresas/${empresaId}/clientes/${customerId}`,
        ),
      );
    } catch {
      // O atendimento continua mesmo se o cartão lateral não atualizar.
    }
  }

  async function createNewContact() {
    if (!empresaId || creatingContact) return;
    setCreatingContact(true);
    setError("");
    const nextSession = newId();
    try {
      const data = await superAdminApiRequest<SimulatorBootstrap>(
        `/simulador-ia/empresas/${empresaId}/novo-contato`,
        {
          method: "POST",
          body: JSON.stringify({ session_id: nextSession, whatsapp: newPhone.trim() || null }),
        },
      );
      setSessionId(nextSession);
      setBootstrap(data);
      setClienteId(String(data.cliente_id));
      setTestContactCreated(data.criado_por_ia && data.novo_contato);
      setMessages([]);
      setDebug(emptyDebug);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Não foi possível criar o contato.");
    } finally {
      setCreatingContact(false);
    }
  }

  async function resetConversation() {
    if (!bootstrap || responding) return;
    try {
      await superAdminApiRequest<SimulatorBootstrap>(
        `/simulador-ia/empresas/${bootstrap.empresa_id}/clientes/${bootstrap.cliente_id}/reset`,
        { method: "POST", body: JSON.stringify({ session_id: sessionId }) },
      );
    } catch {
      // Um novo session id isola a próxima simulação.
    }
    setSessionId(newId());
    setMessages([]);
    setInput("");
    setDebug(emptyDebug);
    setLastModel("—");
    setLastLatency(null);
    await refreshBootstrap();
  }

  async function deleteTestContact() {
    if (!bootstrap || !testContactCreated || responding) return;
    try {
      await superAdminApiRequest<void>(
        `/simulador-ia/empresas/${bootstrap.empresa_id}/clientes/${bootstrap.cliente_id}/contato-teste`,
        { method: "DELETE" },
      );
      setBootstrap(null);
      setClienteId("");
      setMessages([]);
      setDebug(emptyDebug);
      setTestContactCreated(false);
      setNewPhone("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Não foi possível excluir o contato de teste.");
    }
  }

  async function submitCustomerMessage(text: string, actionId?: string) {
    const clean = text.trim();
    if (!clean || responding || !bootstrap || debug.handoff) return;

    const clearedMessages = messages.map((message) => ({ ...message, quickReplies: [] }));
    const clientMessage: ChatMessage = {
      id: `client-${newId()}`,
      remetente: "CLIENTE",
      conteudo: clean,
      createdAt: new Date().toISOString(),
    };
    const nextMessages = [...clearedMessages, clientMessage];
    setMessages(nextMessages);
    setInput("");
    setError("");
    setResponding(true);

    try {
      const response = await superAdminApiRequest<SimulatorReply>(
        `/simulador-ia/empresas/${bootstrap.empresa_id}/clientes/${bootstrap.cliente_id}/responder-autonomo`,
        {
          method: "POST",
          body: JSON.stringify({
            session_id: sessionId,
            action_id: actionId ?? null,
            mensagens: nextMessages.slice(-20).map((message) => ({
              remetente: message.remetente,
              conteudo: message.conteudo,
            })),
          }),
        },
      );

      setMessages((current) => [
        ...current,
        {
          id: response.id_whatsapp,
          remetente: "IA",
          conteudo: response.conteudo,
          createdAt: response.created_at,
          quickReplies: response.handoff ? [] : response.quick_replies ?? [],
        },
      ]);
      setLastModel(response.model);
      setLastLatency(response.latency_ms);
      setDebug({
        intent: response.intent,
        interpretedAs: response.interpreted_as,
        agentState: response.agent_state,
        handoff: response.handoff,
        handoffReason: response.handoff_reason,
        customerComplete: response.customer_complete,
        pendingAction: response.pending_action,
        tools: response.tools,
      });
      await refreshBootstrap(response.customer_id ?? bootstrap.cliente_id);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Não foi possível concluir essa mensagem.");
    } finally {
      setResponding(false);
    }
  }

  function sendTyped(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submitCustomerMessage(input);
  }

  return (
    <div className="super-admin-page super-admin-ai-simulator">
      <header className="super-admin-page-header">
        <div>
          <span>Laboratório autônomo</span>
          <h1>Simulador de IA</h1>
          <p>Teste o fluxo como uma conversa real: o cliente pode clicar ou escrever livremente, e a IA tenta recuperar mensagens imperfeitas antes de pedir ajuda.</p>
        </div>
        <span className="super-admin-simulator-private"><Icon name="lock" size={15} /> Somente Super Admin</span>
      </header>

      {error && <div className="super-admin-alert error">{error}</div>}

      <div className="ai-v2-write-warning">
        Esta simulação agora é espelhada em Conversas da empresa. Cadastros, veículos e operações confirmadas continuam usando o banco de staging.
      </div>

      <section className="super-admin-ai-workspace">
        <aside className="super-admin-ai-control super-admin-card">
          <div className="super-admin-ai-control-title">
            <span><Icon name="bot" size={20} /></span>
            <div><strong>Contexto do teste</strong><small>Cliente real ou primeiro contato</small></div>
          </div>

          <label className="super-admin-ai-field">
            Empresa
            <select
              value={empresaId}
              onChange={(event) => { setEmpresaId(event.target.value); setBusca(""); setNewPhone(""); }}
              disabled={loadingCompanies || responding}
            >
              <option value="">{loadingCompanies ? "Carregando..." : "Selecione uma empresa"}</option>
              {empresas.map((empresa) => <option value={empresa.id} key={empresa.id}>{empresa.nome}</option>)}
            </select>
          </label>

          {empresaId && (
            <div className="ai-v2-lab-mode">
              <button type="button" className={mode === "EXISTENTE" ? "active" : ""} onClick={() => setMode("EXISTENTE")}>Cliente existente</button>
              <button type="button" className={mode === "NOVO" ? "active" : ""} onClick={() => setMode("NOVO")}>Novo contato</button>
            </div>
          )}

          {empresaId && mode === "EXISTENTE" && (
            <>
              <label className="super-admin-ai-field">Buscar cliente
                <div className="super-admin-ai-search"><Icon name="search" size={16} /><input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Nome ou telefone" /></div>
              </label>
              <label className="super-admin-ai-field">Cliente
                <select value={clienteId} onChange={(e) => setClienteId(e.target.value)} disabled={loadingClients}>
                  <option value="">{loadingClients ? "Carregando..." : "Selecione um cliente"}</option>
                  {clientes.map((cliente) => <option value={cliente.id} key={cliente.id}>{cliente.nome}{cliente.whatsapp ? ` · ${cliente.whatsapp}` : ""}</option>)}
                </select>
              </label>
            </>
          )}

          {empresaId && mode === "NOVO" && !bootstrap && (
            <div className="ai-v2-new-contact-box">
              <label className="super-admin-ai-field">WhatsApp fictício
                <input value={newPhone} onChange={(e) => setNewPhone(e.target.value)} placeholder="Opcional" />
              </label>
              <button className="button button-primary" type="button" onClick={() => void createNewContact()} disabled={creatingContact}>
                <Icon name="plus" size={16} /> {creatingContact ? "Criando..." : "Iniciar contato novo"}
              </button>
            </div>
          )}

          {bootstrap && (
            <div className="super-admin-ai-real-data">
              <h2>Contexto atual</h2>
              <div><span>Cliente</span><strong>{bootstrap.cliente}</strong></div>
              <div><span>Empresa</span><strong>{selectedCompany?.nome ?? bootstrap.empresa}</strong></div>
              <div><span>Veículos</span><strong>{bootstrap.veiculos.length}</strong></div>
              <div className="ai-v2-contact-flags">
                {bootstrap.criado_por_ia && <span>criado pela IA</span>}
                <span className={bootstrap.cadastro_completo ? "good" : "danger"}>{bootstrap.cadastro_completo ? "cadastro completo" : "cadastro progressivo"}</span>
              </div>
              {bootstrap.veiculos.map((vehicle) => <small key={vehicle.id}>{vehicleLabel(vehicle)}</small>)}
              <div className="guided-simulation-note">
                <Icon name="chat" size={15} />
                <span><strong>Espelhamento ativo</strong>O atendimento aparece na tela Conversas da empresa enquanto você testa.</span>
              </div>
            </div>
          )}

          <div className="wa-simulator-scenarios">
            <h2>Testes rápidos</h2>
            <div>{scenarios.map((scenario) => <button type="button" key={scenario.label} disabled={!bootstrap || responding || debug.handoff} onClick={() => setInput(scenario.text)}>{scenario.label}</button>)}</div>
          </div>

          <div className="wa-simulator-metrics">
            <div><span>Motor</span><strong>{lastModel}</strong></div>
            <div><span>Resposta</span><strong>{lastLatency === null ? "—" : `${lastLatency} ms`}</strong></div>
            <div><span>Mensagens</span><strong>{messages.length}</strong></div>
          </div>

          <div className="ai-v2-debug-panel">
            <div><h2>Debug</h2><span className="ai-v2-debug-badge">Super Admin</span></div>
            <div className="ai-v2-debug-grid">
              <div><span>Interpretação</span><strong>{debug.interpretedAs || "—"}</strong></div>
              <div><span>Intenção</span><strong>{debug.intent || "—"}</strong></div>
              <div><span>Estado</span><strong>{debug.agentState}</strong></div>
              <div><span>Handoff</span><strong>{debug.handoff ? "SIM" : "NÃO"}</strong></div>
            </div>
            {debug.pendingAction && <div className="ai-v2-tool-item"><strong>Aguardando confirmação</strong><pre>{prettyJson(debug.pendingAction)}</pre></div>}
            {debug.handoffReason && <div className="ai-v2-tool-item"><strong>Motivo do handoff</strong><pre>{debug.handoffReason}</pre></div>}
            {debug.tools.map((tool, index) => <div className="ai-v2-tool-item" key={`${tool.name}-${index}`}><strong>{tool.name}</strong><pre>{prettyJson({ argumentos: tool.arguments, resultado: tool.result })}</pre></div>)}
          </div>

          <button className="wa-simulator-reset" type="button" onClick={() => void resetConversation()} disabled={!bootstrap || responding}><Icon name="refresh" size={16} /> Novo atendimento</button>
          {testContactCreated && bootstrap && <button className="button button-secondary" type="button" onClick={() => void deleteTestContact()} disabled={responding}><Icon name="trash" size={15} /> Excluir contato de teste</button>}
        </aside>

        <section className={`wa-phone-shell super-admin-wa-shell ${!bootstrap ? "is-disabled" : ""}`} aria-label="WhatsApp simulado">
          <header className="wa-phone-header">
            <span className="wa-phone-avatar">{bootstrap?.empresa.charAt(0).toUpperCase() || "F"}</span>
            <div><strong>{bootstrap?.empresa || "Selecione o contexto"}</strong><span>{responding ? "digitando..." : debug.handoff ? "com atendente" : bootstrap ? "online" : "aguardando"}</span></div>
            <span className="wa-phone-sandbox">Sandbox</span>
          </header>

          <div className="wa-phone-encryption-note"><Icon name="lock" size={12} /> WhatsApp simulado · clique nas opções ou escreva normalmente</div>

          <div className="wa-phone-messages">
            {!bootstrap && <div className="super-admin-ai-empty-chat"><Icon name="chat" size={30} /><strong>Escolha empresa e cliente</strong><span>Depois envie “Oi” para iniciar.</span></div>}
            {bootstrap && messages.length === 0 && <div className="super-admin-ai-empty-chat"><Icon name="send" size={28} /><strong>Comece como o cliente</strong><span>Envie “Bom dia”, “Oi” ou escreva diretamente o que precisa.</span></div>}
            {messages.length > 0 && <div className="wa-phone-day-chip">Hoje</div>}
            {messages.map((message, index) => {
              const isLatest = index === messages.length - 1;
              return (
                <div className={`wa-message-row ${message.remetente === "CLIENTE" ? "wa-message-row-client" : "wa-message-row-ai"}`} key={message.id}>
                  <div className="guided-message-stack">
                    <div className="wa-message-bubble"><p>{message.conteudo}</p><span className="wa-message-meta">{messageTime(message.createdAt)}{message.remetente === "CLIENTE" && <b>✓✓</b>}</span></div>
                    {message.remetente === "IA" && Boolean(message.quickReplies?.length) && (
                      <div className="guided-message-options" aria-label="Opções desta mensagem">
                        {message.quickReplies?.map((option) => (
                          <button
                            type="button"
                            className={`guided-message-option guided-message-option-${option.kind}`}
                            key={option.id}
                            disabled={responding || !isLatest || debug.handoff}
                            onClick={() => void submitCustomerMessage(option.label, option.id)}
                          >
                            {option.label}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
            {responding && <div className="wa-message-row wa-message-row-ai"><div className="wa-message-bubble wa-typing-bubble"><span /><span /><span /></div></div>}
            <div ref={endRef} />
          </div>

          {debug.handoff && <div className="wa-phone-error"><Icon name="team" size={15} /><span>A IA pausou e encaminhou o atendimento para uma pessoa da equipe.</span></div>}

          <form className="wa-phone-composer" onSubmit={sendTyped}>
            <textarea
              rows={1}
              value={input}
              maxLength={1800}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder={debug.handoff ? "Atendimento transferido" : "Digite uma mensagem"}
              disabled={responding || !bootstrap || debug.handoff}
            />
            <button type="submit" disabled={responding || !bootstrap || !input.trim() || debug.handoff}><Icon name="send" size={20} /></button>
          </form>
        </section>
      </section>
    </div>
  );
}
