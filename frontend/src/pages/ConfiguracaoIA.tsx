import { useEffect, useState, type FormEvent } from "react";
import { Link, useOutletContext } from "react-router";
import { Icon } from "../components/Icon";
import { Alert, LoadingState, PageHeader } from "../components/UI";
import { apiRequest } from "../services/api";
import { showAppToast } from "../services/feedback";
import type { AppOutletContext } from "../types";
import "../ai-v2.css";

interface KnowledgeItem {
  titulo: string;
  conteudo: string;
}

type MenuAction =
  | "AGENDAR"
  | "CONSULTAR_AGENDAMENTO"
  | "REAGENDAR"
  | "CANCELAR"
  | "SERVICOS_PRECOS"
  | "HUMANO";

interface MenuItem {
  acao: MenuAction;
  rotulo: string;
  ativo: boolean;
  ordem: number;
}

interface AISettings {
  empresa_id: number;
  nome_assistente: string;
  prompt_adicional: string | null;
  saudacao_cliente_novo: string | null;
  saudacao_cliente_conhecido: string | null;
  mensagem_transferencia: string | null;
  mensagem_fora_escopo: string | null;
  mensagem_indisponibilidade: string | null;
  mensagem_despedida: string | null;
  texto_menu_principal: string | null;
  tom: "FORMAL" | "EQUILIBRADO" | "INFORMAL";
  tamanho_resposta: "CURTA" | "MEDIA" | "DETALHADA";
  usar_emojis: boolean;
  criar_cliente_auto: boolean;
  criar_veiculo_auto: boolean;
  pode_agendar: boolean;
  pode_reagendar: boolean;
  pode_cancelar: boolean;
  confirmar_acoes: boolean;
  transferir_fora_escopo: boolean;
  fluxo_guiado_ativo: boolean;
  mostrar_interpretacao: boolean;
  tentativas_antes_handoff: number;
  campos_cliente_obrigatorios: Array<"nome" | "email">;
  campos_veiculo_obrigatorios: Array<"tipo_veiculo" | "marca" | "modelo" | "ano" | "cor">;
  conhecimento: KnowledgeItem[];
  menu_principal: MenuItem[];
}

const defaultMenu: MenuItem[] = [
  { acao: "AGENDAR", rotulo: "Agendar serviço", ativo: true, ordem: 10 },
  { acao: "CONSULTAR_AGENDAMENTO", rotulo: "Consultar agendamento", ativo: true, ordem: 20 },
  { acao: "REAGENDAR", rotulo: "Reagendar", ativo: true, ordem: 30 },
  { acao: "CANCELAR", rotulo: "Cancelar", ativo: true, ordem: 40 },
  { acao: "SERVICOS_PRECOS", rotulo: "Serviços e preços", ativo: true, ordem: 50 },
  { acao: "HUMANO", rotulo: "Falar com atendente", ativo: true, ordem: 60 },
];

const defaultSettings: AISettings = {
  empresa_id: 0,
  nome_assistente: "Assistente",
  prompt_adicional: null,
  saudacao_cliente_novo: "Olá! 👋 Como posso ajudar hoje?",
  saudacao_cliente_conhecido: "Olá, {{primeiro_nome}}! Como podemos ajudar hoje?",
  mensagem_transferencia: "Vou encaminhar seu atendimento para uma pessoa da equipe para conseguirmos te ajudar melhor.",
  mensagem_fora_escopo: "Esse serviço não faz parte do que oferecemos atualmente.",
  mensagem_indisponibilidade: "Não encontrei disponibilidade nesse período. Posso buscar outro horário para você?",
  mensagem_despedida: "Perfeito! Se precisar de mais alguma coisa, estamos por aqui.",
  texto_menu_principal: "Como posso ajudar hoje?",
  tom: "EQUILIBRADO",
  tamanho_resposta: "CURTA",
  usar_emojis: true,
  criar_cliente_auto: true,
  criar_veiculo_auto: true,
  pode_agendar: true,
  pode_reagendar: true,
  pode_cancelar: true,
  confirmar_acoes: true,
  transferir_fora_escopo: true,
  fluxo_guiado_ativo: true,
  mostrar_interpretacao: true,
  tentativas_antes_handoff: 2,
  campos_cliente_obrigatorios: ["nome"],
  campos_veiculo_obrigatorios: ["tipo_veiculo"],
  conhecimento: [],
  menu_principal: defaultMenu,
};

function Toggle({
  checked,
  onChange,
  title,
  description,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  title: string;
  description: string;
}) {
  return (
    <label className="ai-v2-toggle-row">
      <div>
        <strong>{title}</strong>
        <span>{description}</span>
      </div>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
    </label>
  );
}

export function ConfiguracaoIA() {
  const { usuario } = useOutletContext<AppOutletContext>();
  const [data, setData] = useState<AISettings>(defaultSettings);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const canEdit = usuario.cargo === "ADMIN" || usuario.cargo === "GERENTE";

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError("");
      try {
        const response = await apiRequest<AISettings>("/configuracoes/ia-operacional");
        setData({
          ...defaultSettings,
          ...response,
          conhecimento: response.conhecimento ?? [],
          menu_principal: (response.menu_principal?.length ? response.menu_principal : defaultMenu)
            .slice()
            .sort((a, b) => a.ordem - b.ordem),
        });
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Não foi possível carregar a IA.");
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, []);

  function set<K extends keyof AISettings>(key: K, value: AISettings[K]) {
    setData((current) => ({ ...current, [key]: value }));
  }

  function toggleRequiredClient(field: "nome" | "email") {
    set(
      "campos_cliente_obrigatorios",
      data.campos_cliente_obrigatorios.includes(field)
        ? data.campos_cliente_obrigatorios.filter((item) => item !== field)
        : [...data.campos_cliente_obrigatorios, field],
    );
  }

  function toggleRequiredVehicle(field: "tipo_veiculo" | "marca" | "modelo" | "ano" | "cor") {
    set(
      "campos_veiculo_obrigatorios",
      data.campos_veiculo_obrigatorios.includes(field)
        ? data.campos_veiculo_obrigatorios.filter((item) => item !== field)
        : [...data.campos_veiculo_obrigatorios, field],
    );
  }

  function updateMenu(index: number, patch: Partial<MenuItem>) {
    set(
      "menu_principal",
      data.menu_principal.map((item, position) => (position === index ? { ...item, ...patch } : item)),
    );
  }

  function moveMenu(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= data.menu_principal.length) return;
    const next = [...data.menu_principal];
    [next[index], next[target]] = [next[target], next[index]];
    set(
      "menu_principal",
      next.map((item, position) => ({ ...item, ordem: (position + 1) * 10 })),
    );
  }

  function addKnowledge() {
    set("conhecimento", [...data.conhecimento, { titulo: "", conteudo: "" }]);
  }

  function updateKnowledge(index: number, patch: Partial<KnowledgeItem>) {
    set(
      "conhecimento",
      data.conhecimento.map((item, position) => (position === index ? { ...item, ...patch } : item)),
    );
  }

  function removeKnowledge(index: number) {
    set("conhecimento", data.conhecimento.filter((_, position) => position !== index));
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canEdit) return;
    const knowledge = data.conhecimento
      .map((item) => ({ titulo: item.titulo.trim(), conteudo: item.conteudo.trim() }))
      .filter((item) => item.titulo && item.conteudo);
    const menu = data.menu_principal.map((item, index) => ({
      ...item,
      rotulo: item.rotulo.trim() || defaultMenu.find((entry) => entry.acao === item.acao)?.rotulo || item.acao,
      ordem: (index + 1) * 10,
    }));
    setSaving(true);
    setError("");
    try {
      const response = await apiRequest<AISettings>("/configuracoes/ia-operacional", {
        method: "PUT",
        body: JSON.stringify({ ...data, conhecimento: knowledge, menu_principal: menu }),
      });
      setData({ ...defaultSettings, ...response });
      showAppToast("Configuração da IA salva com sucesso.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Não foi possível salvar a IA.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page ai-v2-settings-page">
      <PageHeader
        eyebrow="Atendimento automatizado"
        title="Configuração da IA"
        description="Defina como a assistente conversa, quais ações pode executar e como o cliente navega pelas opções rápidas."
        actions={
          <Link className="button button-secondary" to="/configuracoes">
            <Icon name="arrow-left" size={17} />
            Voltar
          </Link>
        }
      />

      {error && <Alert>{error}</Alert>}
      {loading ? (
        <LoadingState label="Carregando configuração da IA..." />
      ) : (
        <form className="ai-v2-settings-stack" onSubmit={save}>
          {!canEdit && <Alert type="info">Somente administradores e gerentes podem alterar a IA.</Alert>}

          <section className="content-card ai-v2-card">
            <div className="card-heading">
              <div><span>Identidade</span><h2>Como a assistente deve conversar</h2></div>
              <Icon name="bot" size={24} />
            </div>
            <div className="ai-v2-form-grid three">
              <label className="field">Nome da assistente
                <input value={data.nome_assistente} maxLength={80} disabled={!canEdit || saving} onChange={(e) => set("nome_assistente", e.target.value)} />
              </label>
              <label className="field">Tom
                <select value={data.tom} disabled={!canEdit || saving} onChange={(e) => set("tom", e.target.value as AISettings["tom"])}>
                  <option value="FORMAL">Formal</option>
                  <option value="EQUILIBRADO">Equilibrado</option>
                  <option value="INFORMAL">Informal</option>
                </select>
              </label>
              <label className="field">Tamanho das respostas
                <select value={data.tamanho_resposta} disabled={!canEdit || saving} onChange={(e) => set("tamanho_resposta", e.target.value as AISettings["tamanho_resposta"])}>
                  <option value="CURTA">Curta</option>
                  <option value="MEDIA">Média</option>
                  <option value="DETALHADA">Detalhada</option>
                </select>
              </label>
            </div>
            <Toggle checked={data.usar_emojis} onChange={(value) => set("usar_emojis", value)} title="Usar emojis" description="Permite emojis com moderação para deixar a conversa mais natural." />
            <label className="field">Orientações adicionais da empresa
              <textarea rows={4} value={data.prompt_adicional ?? ""} disabled={!canEdit || saving} placeholder="Ex.: nunca ofereça desconto sem autorização." onChange={(e) => set("prompt_adicional", e.target.value || null)} />
              <small className="field-help">Essas orientações complementam as regras de segurança do FlowDeskIA.</small>
            </label>
          </section>

          <section className="content-card ai-v2-card">
            <div className="card-heading">
              <div><span>Navegação</span><h2>Fluxo guiado e opções rápidas</h2></div>
              <Icon name="chat" size={24} />
            </div>
            <div className="ai-v2-toggle-grid">
              <Toggle checked={data.fluxo_guiado_ativo} onChange={(value) => set("fluxo_guiado_ativo", value)} title="Usar fluxo guiado" description="Apresenta opções clicáveis e usa a IA para interpretar mensagens livres como atalhos para os mesmos fluxos." />
              <Toggle checked={data.mostrar_interpretacao} onChange={(value) => set("mostrar_interpretacao", value)} title="Mostrar o que foi interpretado" description="Ex.: “Entendi que você quer realizar um agendamento” antes de abrir as opções correspondentes." />
            </div>
            <label className="field">Texto acima do menu principal
              <input value={data.texto_menu_principal ?? ""} maxLength={500} disabled={!canEdit || saving} onChange={(e) => set("texto_menu_principal", e.target.value || null)} placeholder="Como posso ajudar hoje?" />
            </label>
            <div className="ai-v2-knowledge-list">
              {data.menu_principal.map((item, index) => (
                <article className="ai-v2-knowledge-item" key={item.acao}>
                  <div className="ai-v2-menu-row">
                    <label>
                      <input type="checkbox" checked={item.ativo} disabled={!canEdit || saving} onChange={(e) => updateMenu(index, { ativo: e.target.checked })} />
                      <strong>{item.acao.replaceAll("_", " ")}</strong>
                    </label>
                    <div>
                      <button type="button" className="button button-secondary" disabled={!canEdit || saving || index === 0} onClick={() => moveMenu(index, -1)}>↑</button>
                      <button type="button" className="button button-secondary" disabled={!canEdit || saving || index === data.menu_principal.length - 1} onClick={() => moveMenu(index, 1)}>↓</button>
                    </div>
                  </div>
                  <input value={item.rotulo} maxLength={40} disabled={!canEdit || saving} onChange={(e) => updateMenu(index, { rotulo: e.target.value })} placeholder="Texto do botão" />
                </article>
              ))}
            </div>
            <small className="field-help">A ordem acima é a ordem mostrada ao cliente. Recursos desativados em Autonomia são removidos do menu automaticamente.</small>
          </section>

          <section className="content-card ai-v2-card">
            <div className="card-heading">
              <div><span>Mensagens</span><h2>Saudações e respostas padrão</h2></div>
              <Icon name="chat" size={24} />
            </div>
            <div className="ai-v2-form-grid two">
              <label className="field">Cliente novo
                <textarea rows={3} value={data.saudacao_cliente_novo ?? ""} disabled={!canEdit || saving} onChange={(e) => set("saudacao_cliente_novo", e.target.value || null)} />
              </label>
              <label className="field">Cliente conhecido
                <textarea rows={3} value={data.saudacao_cliente_conhecido ?? ""} disabled={!canEdit || saving} onChange={(e) => set("saudacao_cliente_conhecido", e.target.value || null)} />
              </label>
              <label className="field">Transferência para humano
                <textarea rows={3} value={data.mensagem_transferencia ?? ""} disabled={!canEdit || saving} onChange={(e) => set("mensagem_transferencia", e.target.value || null)} />
              </label>
              <label className="field">Pedido fora do escopo
                <textarea rows={3} value={data.mensagem_fora_escopo ?? ""} disabled={!canEdit || saving} onChange={(e) => set("mensagem_fora_escopo", e.target.value || null)} />
              </label>
              <label className="field">Sem horário disponível
                <textarea rows={3} value={data.mensagem_indisponibilidade ?? ""} disabled={!canEdit || saving} onChange={(e) => set("mensagem_indisponibilidade", e.target.value || null)} />
              </label>
              <label className="field">Despedida
                <textarea rows={3} value={data.mensagem_despedida ?? ""} disabled={!canEdit || saving} onChange={(e) => set("mensagem_despedida", e.target.value || null)} />
              </label>
            </div>
            <div className="ai-v2-template-help">Variáveis: <code>{"{{primeiro_nome}}"}</code>, <code>{"{{nome_cliente}}"}</code>, <code>{"{{nome_assistente}}"}</code> e <code>{"{{empresa}}"}</code>.</div>
          </section>

          <section className="content-card ai-v2-card">
            <div className="card-heading">
              <div><span>Autonomia</span><h2>O que a IA pode fazer sozinha</h2></div>
              <Icon name="settings" size={24} />
            </div>
            <div className="ai-v2-toggle-grid">
              <Toggle checked={data.criar_cliente_auto} onChange={(value) => set("criar_cliente_auto", value)} title="Criar clientes automaticamente" description="Novos contatos entram como cadastro progressivo usando o identificador do canal." />
              <Toggle checked={data.criar_veiculo_auto} onChange={(value) => set("criar_veiculo_auto", value)} title="Cadastrar veículos" description="Grava veículo somente quando os dados informados estiverem claros." />
              <Toggle checked={data.pode_agendar} onChange={(value) => set("pode_agendar", value)} title="Agendar" description="Consulta a agenda real e cria o agendamento após confirmação." />
              <Toggle checked={data.pode_reagendar} onChange={(value) => set("pode_reagendar", value)} title="Reagendar" description="Troca data e horário após validar disponibilidade e confirmação." />
              <Toggle checked={data.pode_cancelar} onChange={(value) => set("pode_cancelar", value)} title="Cancelar" description="Cancela horários do próprio cliente após confirmação." />
              <Toggle checked={data.confirmar_acoes} onChange={(value) => set("confirmar_acoes", value)} title="Exigir confirmação explícita" description="Proteção recomendada antes de agendar, cancelar ou reagendar." />
              <Toggle checked={data.transferir_fora_escopo} onChange={(value) => set("transferir_fora_escopo", value)} title="Transferir pedidos fora do escopo" description="Ex.: uma estética automotiva recebe pedido de tosa de cachorro." />
            </div>
            <label className="field ai-v2-small-field">Tentativas sem entender antes do handoff
              <select value={data.tentativas_antes_handoff} disabled={!canEdit || saving} onChange={(e) => set("tentativas_antes_handoff", Number(e.target.value))}>
                {[1, 2, 3, 4, 5].map((value) => <option value={value} key={value}>{value}</option>)}
              </select>
            </label>
          </section>

          <section className="content-card ai-v2-card">
            <div className="card-heading">
              <div><span>Cadastro progressivo</span><h2>Dados necessários para concluir operações</h2></div>
              <Icon name="user" size={24} />
            </div>
            <div className="ai-v2-required-grid">
              <div>
                <strong>Cliente</strong>
                <label><input type="checkbox" checked={data.campos_cliente_obrigatorios.includes("nome")} onChange={() => toggleRequiredClient("nome")} disabled={!canEdit || saving} /> Nome</label>
                <label><input type="checkbox" checked={data.campos_cliente_obrigatorios.includes("email")} onChange={() => toggleRequiredClient("email")} disabled={!canEdit || saving} /> E-mail</label>
                <small>WhatsApp já vem do próprio canal.</small>
              </div>
              <div>
                <strong>Veículo</strong>
                {(["tipo_veiculo", "marca", "modelo", "ano", "cor"] as const).map((field) => (
                  <label key={field}><input type="checkbox" checked={data.campos_veiculo_obrigatorios.includes(field)} onChange={() => toggleRequiredVehicle(field)} disabled={!canEdit || saving} /> {field === "tipo_veiculo" ? "Tipo do veículo" : field.charAt(0).toUpperCase() + field.slice(1)}</label>
                ))}
                <small>A IA coleta apenas quando necessário.</small>
              </div>
            </div>
          </section>

          <section className="content-card ai-v2-card">
            <div className="card-heading">
              <div><span>Conhecimento</span><h2>Informações que a IA pode usar</h2></div>
              <Icon name="info" size={24} />
            </div>
            <p className="ai-v2-section-copy">Cadastre formas de pagamento, região atendida, busca e entrega, políticas, garantias e perguntas frequentes.</p>
            <div className="ai-v2-knowledge-list">
              {data.conhecimento.map((item, index) => (
                <article className="ai-v2-knowledge-item" key={index}>
                  <input value={item.titulo} maxLength={120} disabled={!canEdit || saving} placeholder="Título" onChange={(e) => updateKnowledge(index, { titulo: e.target.value })} />
                  <textarea rows={3} value={item.conteudo} maxLength={1200} disabled={!canEdit || saving} placeholder="Conteúdo que a IA pode informar" onChange={(e) => updateKnowledge(index, { conteudo: e.target.value })} />
                  <button type="button" className="button button-secondary" onClick={() => removeKnowledge(index)} disabled={!canEdit || saving}><Icon name="trash" size={15} /> Remover</button>
                </article>
              ))}
              {data.conhecimento.length === 0 && <div className="compact-empty">Nenhum conhecimento adicional cadastrado.</div>}
            </div>
            <button type="button" className="button button-secondary" onClick={addKnowledge} disabled={!canEdit || saving}><Icon name="plus" size={16} /> Adicionar informação</button>
          </section>

          <div className="ai-v2-save-bar">
            <span>Regras de segurança, confirmação e isolamento de dados continuam controladas pelo FlowDeskIA.</span>
            <button className="button button-primary" type="submit" disabled={!canEdit || saving}>{saving ? "Salvando..." : "Salvar configuração da IA"}</button>
          </div>
        </form>
      )}
    </div>
  );
}
