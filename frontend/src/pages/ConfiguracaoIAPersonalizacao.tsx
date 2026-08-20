import { useEffect, useState, type FormEvent } from "react";
import { Link, useOutletContext } from "react-router";
import { Icon } from "../components/Icon";
import { Alert, LoadingState, PageHeader } from "../components/UI";
import { apiRequest } from "../services/api";
import { showAppToast } from "../services/feedback";
import type { AppOutletContext } from "../types";
import "../ai-v2.css";


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

interface BasicQuestions {
  servico: string;
  nome: string;
  email: string;
  veiculo_novo: string;
  veiculo_existente: string;
  data_agendamento: string;
  data_reagendamento: string;
  horario: string;
  consulta_agendamento: string;
  cancelamento: string;
  reagendamento: string;
}

interface PersonalizationSettings {
  empresa_id: number;
  texto_menu_principal: string | null;
  menu_principal: MenuItem[];
  perguntas_basicas: BasicQuestions;
}

const defaultMenu: MenuItem[] = [
  { acao: "AGENDAR", rotulo: "Agendar serviço", ativo: true, ordem: 10 },
  { acao: "CONSULTAR_AGENDAMENTO", rotulo: "Consultar agendamento", ativo: true, ordem: 20 },
  { acao: "REAGENDAR", rotulo: "Reagendar", ativo: true, ordem: 30 },
  { acao: "CANCELAR", rotulo: "Cancelar", ativo: true, ordem: 40 },
  { acao: "SERVICOS_PRECOS", rotulo: "Serviços e preços", ativo: true, ordem: 50 },
  { acao: "HUMANO", rotulo: "Falar com atendente", ativo: true, ordem: 60 },
];

const defaultQuestions: BasicQuestions = {
  servico: "Qual serviço você quer agendar?",
  nome: "Antes de continuar, qual é o seu nome?",
  email: "Qual é o seu e-mail?",
  veiculo_novo: "Qual é o seu carro? Pode escrever só o modelo, por exemplo: Corsa, Corolla, Civic, Onix ou Hilux.",
  veiculo_existente: "Qual veículo você quer usar neste agendamento?",
  data_agendamento: "Para qual dia você prefere?",
  data_reagendamento: "Para qual nova data você prefere reagendar?",
  horario: "Encontrei estes horários para {{data}}. Qual você prefere?",
  consulta_agendamento: "Encontrei estes agendamentos. Qual você quer consultar?",
  cancelamento: "Qual agendamento você quer cancelar?",
  reagendamento: "Qual agendamento você quer reagendar?",
};

const defaultSettings: PersonalizationSettings = {
  empresa_id: 0,
  texto_menu_principal: "Como posso ajudar hoje?",
  menu_principal: defaultMenu,
  perguntas_basicas: defaultQuestions,
};

const questionFields: Array<{
  key: keyof BasicQuestions;
  label: string;
  help: string;
}> = [
  { key: "servico", label: "Escolha do serviço", help: "Pergunta exibida antes de mostrar os serviços disponíveis." },
  { key: "nome", label: "Nome do cliente", help: "Usada quando o nome ainda precisa ser coletado." },
  { key: "email", label: "E-mail", help: "Usada somente quando o e-mail estiver configurado como obrigatório." },
  { key: "veiculo_novo", label: "Veículo novo", help: "Pergunta livre para identificar automaticamente o carro do cliente." },
  { key: "veiculo_existente", label: "Escolha de veículo cadastrado", help: "Exibida quando o cliente já possui mais de um veículo." },
  { key: "data_agendamento", label: "Data do agendamento", help: "Acompanha os botões Hoje, Amanhã e outras datas." },
  { key: "data_reagendamento", label: "Nova data do reagendamento", help: "Pergunta usada ao trocar a data de um atendimento." },
  { key: "horario", label: "Escolha do horário", help: "Use {{data}} para inserir automaticamente a data selecionada." },
  { key: "consulta_agendamento", label: "Consultar agendamento", help: "Exibida quando houver mais de um agendamento ativo." },
  { key: "cancelamento", label: "Escolha para cancelar", help: "Pergunta antes da seleção do agendamento que será cancelado." },
  { key: "reagendamento", label: "Escolha para reagendar", help: "Pergunta antes da seleção do agendamento que será alterado." },
];

const actionLabels: Record<MenuAction, string> = {
  AGENDAR: "Agendar",
  CONSULTAR_AGENDAMENTO: "Consultar agendamento",
  REAGENDAR: "Reagendar",
  CANCELAR: "Cancelar",
  SERVICOS_PRECOS: "Serviços e preços",
  HUMANO: "Atendimento humano",
};

export function ConfiguracaoIAPersonalizacao() {
  const { usuario } = useOutletContext<AppOutletContext>();
  const [data, setData] = useState<PersonalizationSettings>(defaultSettings);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const canEdit = usuario.cargo === "ADMIN" || usuario.cargo === "GERENTE";

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError("");
      try {
        const response = await apiRequest<PersonalizationSettings>("/configuracoes/ia-personalizacao");
        setData({
          ...defaultSettings,
          ...response,
          menu_principal: (response.menu_principal?.length ? response.menu_principal : defaultMenu)
            .slice()
            .sort((a, b) => a.ordem - b.ordem),
          perguntas_basicas: { ...defaultQuestions, ...(response.perguntas_basicas ?? {}) },
        });
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Não foi possível carregar a personalização da IA.");
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, []);

  function updateMenu(index: number, patch: Partial<MenuItem>) {
    setData((current) => ({
      ...current,
      menu_principal: current.menu_principal.map((item, position) =>
        position === index ? { ...item, ...patch } : item,
      ),
    }));
  }

  function moveMenu(index: number, direction: -1 | 1) {
    setData((current) => {
      const target = index + direction;
      if (target < 0 || target >= current.menu_principal.length) return current;
      const next = [...current.menu_principal];
      [next[index], next[target]] = [next[target], next[index]];
      return {
        ...current,
        menu_principal: next.map((item, position) => ({ ...item, ordem: (position + 1) * 10 })),
      };
    });
  }

  function updateQuestion(key: keyof BasicQuestions, value: string) {
    setData((current) => ({
      ...current,
      perguntas_basicas: { ...current.perguntas_basicas, [key]: value },
    }));
  }

  function restoreDefaults() {
    setData((current) => ({
      ...current,
      texto_menu_principal: "Como posso ajudar hoje?",
      menu_principal: defaultMenu.map((item) => ({ ...item })),
      perguntas_basicas: { ...defaultQuestions },
    }));
    showAppToast("Textos padrão restaurados. Clique em Salvar para aplicar.");
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canEdit) return;

    const menu = data.menu_principal.map((item, index) => ({
      ...item,
      rotulo: item.rotulo.trim() || defaultMenu.find((entry) => entry.acao === item.acao)?.rotulo || item.acao,
      ordem: (index + 1) * 10,
    }));
    const questions = Object.fromEntries(
      Object.entries(data.perguntas_basicas).map(([key, value]) => [
        key,
        value.trim() || defaultQuestions[key as keyof BasicQuestions],
      ]),
    ) as unknown as BasicQuestions;

    setSaving(true);
    setError("");
    try {
      const response = await apiRequest<PersonalizationSettings>("/configuracoes/ia-personalizacao", {
        method: "PUT",
        body: JSON.stringify({
          texto_menu_principal: data.texto_menu_principal?.trim() || null,
          menu_principal: menu,
          perguntas_basicas: questions,
        }),
      });
      setData({
        ...response,
        menu_principal: response.menu_principal.slice().sort((a, b) => a.ordem - b.ordem),
        perguntas_basicas: { ...defaultQuestions, ...response.perguntas_basicas },
      });
      showAppToast("Personalização da IA salva com sucesso.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Não foi possível salvar a personalização da IA.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page ai-v2-settings-page">
      <PageHeader
        eyebrow="Inteligência artificial"
        title="Personalização do atendimento"
        description="Edite o que o cliente vê nos botões e nas perguntas principais sem alterar a lógica interna da IA."
        actions={
          <div className="page-header-actions">
            <Link className="button button-secondary" to="/configuracoes">
              <Icon name="arrow-left" size={17} />
              Voltar
            </Link>
          </div>
        }
      />

      {error && <Alert>{error}</Alert>}
      {loading ? (
        <LoadingState label="Carregando personalização da IA..." />
      ) : (
        <form className="ai-v2-settings-stack" onSubmit={save}>
          {!canEdit && <Alert type="info">Somente administradores e gerentes podem alterar estes textos.</Alert>}

          <section className="content-card ai-v2-card">
            <div className="card-heading">
              <div><span>Menu principal</span><h2>Botões de escolha do cliente</h2></div>
              <Icon name="chat" size={24} />
            </div>
            <p className="ai-v2-section-copy">
              O texto pode mudar, mas cada botão continua ligado à mesma ação interna. Assim a personalização não quebra agendamento, cancelamento ou handoff.
            </p>
            <label className="field">Pergunta acima dos botões
              <input
                value={data.texto_menu_principal ?? ""}
                maxLength={500}
                disabled={!canEdit || saving}
                placeholder="Como posso ajudar hoje?"
                onChange={(event) => setData((current) => ({ ...current, texto_menu_principal: event.target.value || null }))}
              />
            </label>

            <div className="ai-v2-knowledge-list">
              {data.menu_principal.map((item, index) => (
                <article className="ai-v2-knowledge-item" key={item.acao}>
                  <div className="ai-v2-menu-row">
                    <label>
                      <input
                        type="checkbox"
                        checked={item.ativo}
                        disabled={!canEdit || saving}
                        onChange={(event) => updateMenu(index, { ativo: event.target.checked })}
                      />
                      <strong>{actionLabels[item.acao]}</strong>
                    </label>
                    <div>
                      <button type="button" className="button button-secondary" disabled={!canEdit || saving || index === 0} onClick={() => moveMenu(index, -1)}>↑</button>
                      <button type="button" className="button button-secondary" disabled={!canEdit || saving || index === data.menu_principal.length - 1} onClick={() => moveMenu(index, 1)}>↓</button>
                    </div>
                  </div>
                  <input
                    value={item.rotulo}
                    maxLength={40}
                    disabled={!canEdit || saving}
                    onChange={(event) => updateMenu(index, { rotulo: event.target.value })}
                    placeholder="Texto do botão"
                  />
                </article>
              ))}
            </div>
          </section>

          <section className="content-card ai-v2-card">
            <div className="card-heading">
              <div><span>Conversa</span><h2>Perguntas básicas do atendimento</h2></div>
              <Icon name="bot" size={24} />
            </div>
            <p className="ai-v2-section-copy">
              Esses textos aparecem apenas nos momentos correspondentes do fluxo. O cliente continua podendo responder livremente em vez de usar os botões.
            </p>
            <div className="ai-v2-form-grid two">
              {questionFields.map((field) => (
                <label className="field" key={field.key}>
                  {field.label}
                  <textarea
                    rows={3}
                    value={data.perguntas_basicas[field.key]}
                    maxLength={field.key === "veiculo_novo" ? 400 : 300}
                    disabled={!canEdit || saving}
                    onChange={(event) => updateQuestion(field.key, event.target.value)}
                  />
                  <small className="field-help">{field.help}</small>
                </label>
              ))}
            </div>
            <div className="ai-v2-template-help">
              Variáveis disponíveis: <code>{"{{primeiro_nome}}"}</code>, <code>{"{{nome_cliente}}"}</code>, <code>{"{{empresa}}"}</code>, <code>{"{{data}}"}</code> e <code>{"{{servico}}"}</code>.
            </div>
          </section>

          <section className="content-card ai-v2-card">
            <div className="card-heading">
              <div><span>Prévia</span><h2>Como o menu principal ficará</h2></div>
              <Icon name="info" size={24} />
            </div>
            <div className="ai-v2-knowledge-item">
              <strong>{data.texto_menu_principal || "Como posso ajudar hoje?"}</strong>
              <div className="page-header-actions">
                {data.menu_principal.filter((item) => item.ativo).map((item) => (
                  <span className="button button-secondary" key={item.acao}>{item.rotulo || actionLabels[item.acao]}</span>
                ))}
              </div>
            </div>
          </section>

          <div className="ai-v2-save-bar">
            <button type="button" className="button button-secondary" onClick={restoreDefaults} disabled={!canEdit || saving}>
              Restaurar textos padrão
            </button>
            <button className="button button-primary" type="submit" disabled={!canEdit || saving}>
              {saving ? "Salvando..." : "Salvar personalização"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
