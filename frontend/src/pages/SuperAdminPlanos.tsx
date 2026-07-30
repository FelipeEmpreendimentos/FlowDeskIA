import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Icon } from "../components/Icon";
import { superAdminApiRequest } from "../services/superAdminApi";
import type { PlanoSuperAdmin } from "../types/superAdmin";
import { formatCurrency } from "../utils/format";

const recursosDisponiveis = [
  ["AGENDA", "Agenda"],
  ["CLIENTES", "Clientes"],
  ["VEICULOS", "Veículos"],
  ["SERVICOS", "Serviços"],
  ["CONVERSAS", "Conversas"],
  ["NOTIFICACOES", "Notificações"],
  ["WHATSAPP", "WhatsApp"],
  ["INSTAGRAM", "Instagram"],
  ["AVALIACOES", "Avaliações"],
  ["RELATORIOS", "Relatórios"],
  ["AUTOMACOES", "Automações"],
  ["MULTIPLAS_UNIDADES", "Múltiplas unidades"],
  ["SUPORTE_PRIORITARIO", "Suporte prioritário"],
] as const;

type PlanoForm = {
  codigo: string;
  nome: string;
  descricao: string;
  preco: string;
  preco_anual: string;
  ativo: boolean;
  periodo_teste_dias: string;
  limite_usuarios: string;
  limite_clientes: string;
  limite_agendamentos_mes: string;
  limite_conversas_mes: string;
  limite_mensagens_ia_mes: string;
  limite_canais: string;
  limite_armazenamento_mb: string;
  ia_incluida: boolean;
  ia_adicional_disponivel: boolean;
  recursos: Record<string, boolean>;
};

function emptyResources(): Record<string, boolean> {
  return Object.fromEntries(recursosDisponiveis.map(([key]) => [key, false]));
}

function newPlanForm(): PlanoForm {
  return {
    codigo: "",
    nome: "",
    descricao: "",
    preco: "0.00",
    preco_anual: "",
    ativo: true,
    periodo_teste_dias: "14",
    limite_usuarios: "",
    limite_clientes: "",
    limite_agendamentos_mes: "",
    limite_conversas_mes: "",
    limite_mensagens_ia_mes: "0",
    limite_canais: "",
    limite_armazenamento_mb: "",
    ia_incluida: false,
    ia_adicional_disponivel: true,
    recursos: emptyResources(),
  };
}

function formFromPlan(plan: PlanoSuperAdmin): PlanoForm {
  return {
    codigo: plan.codigo,
    nome: plan.nome,
    descricao: plan.descricao ?? "",
    preco: String(plan.preco),
    preco_anual: plan.preco_anual == null ? "" : String(plan.preco_anual),
    ativo: plan.ativo,
    periodo_teste_dias: String(plan.periodo_teste_dias),
    limite_usuarios: plan.limite_usuarios == null ? "" : String(plan.limite_usuarios),
    limite_clientes: plan.limite_clientes == null ? "" : String(plan.limite_clientes),
    limite_agendamentos_mes:
      plan.limite_agendamentos_mes == null ? "" : String(plan.limite_agendamentos_mes),
    limite_conversas_mes:
      plan.limite_conversas_mes == null ? "" : String(plan.limite_conversas_mes),
    limite_mensagens_ia_mes:
      plan.limite_mensagens_ia_mes == null ? "" : String(plan.limite_mensagens_ia_mes),
    limite_canais: plan.limite_canais == null ? "" : String(plan.limite_canais),
    limite_armazenamento_mb:
      plan.limite_armazenamento_mb == null ? "" : String(plan.limite_armazenamento_mb),
    ia_incluida: plan.ia_incluida,
    ia_adicional_disponivel: plan.ia_adicional_disponivel,
    recursos: { ...emptyResources(), ...plan.recursos },
  };
}

const nullableNumber = (value: string): number | null =>
  value.trim() === "" ? null : Number(value);

export function SuperAdminPlanos() {
  const [planos, setPlanos] = useState<PlanoSuperAdmin[]>([]);
  const [editando, setEditando] = useState<PlanoSuperAdmin | null>(null);
  const [modalAberto, setModalAberto] = useState(false);
  const [form, setForm] = useState<PlanoForm>(newPlanForm());
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");

  async function carregar() {
    setCarregando(true);
    try {
      setPlanos(await superAdminApiRequest<PlanoSuperAdmin[]>("/planos"));
      setErro("");
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível carregar os planos.");
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

  const ativos = useMemo(() => planos.filter((item) => item.ativo).length, [planos]);

  function abrirNovo() {
    setEditando(null);
    setForm(newPlanForm());
    setErro("");
    setModalAberto(true);
  }

  function abrirEdicao(plan: PlanoSuperAdmin) {
    setEditando(plan);
    setForm(formFromPlan(plan));
    setErro("");
    setModalAberto(true);
  }

  function fecharModal() {
    if (salvando) return;
    setModalAberto(false);
    setEditando(null);
    setErro("");
  }

  async function salvar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSalvando(true);
    setErro("");

    const payload = {
      ...(!editando ? { codigo: form.codigo.trim().toUpperCase() } : {}),
      nome: form.nome.trim(),
      descricao: form.descricao.trim() || null,
      preco: Number(form.preco.replace(",", ".")),
      preco_anual:
        form.preco_anual.trim() === ""
          ? null
          : Number(form.preco_anual.replace(",", ".")),
      ativo: form.ativo,
      periodo_teste_dias: Number(form.periodo_teste_dias),
      limite_usuarios: nullableNumber(form.limite_usuarios),
      limite_clientes: nullableNumber(form.limite_clientes),
      limite_agendamentos_mes: nullableNumber(form.limite_agendamentos_mes),
      limite_conversas_mes: nullableNumber(form.limite_conversas_mes),
      limite_mensagens_ia_mes: nullableNumber(form.limite_mensagens_ia_mes),
      limite_canais: nullableNumber(form.limite_canais),
      limite_armazenamento_mb: nullableNumber(form.limite_armazenamento_mb),
      ia_incluida: form.ia_incluida,
      ia_adicional_disponivel: form.ia_adicional_disponivel,
      recursos: form.recursos,
    };

    try {
      if (editando) {
        await superAdminApiRequest<PlanoSuperAdmin>(`/planos/${editando.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        setSucesso("Plano atualizado com sucesso.");
      } else {
        await superAdminApiRequest<PlanoSuperAdmin>("/planos", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setSucesso("Plano criado com sucesso.");
      }
      setModalAberto(false);
      await carregar();
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível salvar o plano.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="super-admin-page">
      <header className="super-admin-page-header">
        <div>
          <span>Catálogo comercial</span>
          <h1>Planos</h1>
          <p>Os planos padrão já estão criados e podem ser alterados a qualquer momento.</p>
        </div>
        <button className="super-admin-primary-button" type="button" onClick={abrirNovo}>
          <Icon name="plus" size={18} />
          Novo plano
        </button>
      </header>

      {sucesso && <div className="super-admin-toast success">{sucesso}</div>}
      {erro && !modalAberto && <div className="super-admin-alert error">{erro}</div>}

      <section className="super-admin-summary-strip">
        <article><strong>{planos.length}</strong><span>Planos cadastrados</span></article>
        <article><strong>{ativos}</strong><span>Planos ativos</span></article>
        <article><strong>14</strong><span>Dias de teste padrão</span></article>
        <article><strong>Todos</strong><span>Permitem adicional de IA</span></article>
      </section>

      {carregando ? (
        <div className="super-admin-state">Carregando planos...</div>
      ) : (
        <section className="super-admin-plan-grid">
          {planos.map((plan) => (
            <article className={`super-admin-plan-card ${!plan.ativo ? "inactive" : ""}`} key={plan.id}>
              <header>
                <div>
                  <span>{plan.codigo}</span>
                  <h2>{plan.nome}</h2>
                </div>
                <span className={`super-admin-status ${plan.ativo ? "active" : "inactive"}`}>
                  {plan.ativo ? "Ativo" : "Inativo"}
                </span>
              </header>
              <p>{plan.descricao ?? "Sem descrição."}</p>
              <div className="super-admin-plan-price">
                <strong>{formatCurrency(plan.preco)}</strong>
                <span>/ mês</span>
              </div>
              <dl>
                <div><dt>Usuários</dt><dd>{plan.limite_usuarios ?? "Ilimitado"}</dd></div>
                <div><dt>Clientes</dt><dd>{plan.limite_clientes ?? "Ilimitado"}</dd></div>
                <div><dt>Agendamentos/mês</dt><dd>{plan.limite_agendamentos_mes ?? "Ilimitado"}</dd></div>
                <div><dt>Conversas/mês</dt><dd>{plan.limite_conversas_mes ?? "Ilimitado"}</dd></div>
                <div><dt>IA incluída</dt><dd>{plan.ia_incluida ? "Sim" : "Não"}</dd></div>
                <div><dt>IA adicional</dt><dd>{plan.ia_adicional_disponivel ? "Disponível" : "Não"}</dd></div>
              </dl>
              <button type="button" onClick={() => abrirEdicao(plan)}>
                <Icon name="edit" size={17} />
                Editar plano
              </button>
            </article>
          ))}
        </section>
      )}

      {modalAberto && (
        <div className="super-admin-modal-backdrop" role="presentation">
          <section className="super-admin-modal large" role="dialog" aria-modal="true">
            <header>
              <div><span>Configuração comercial</span><h2>{editando ? `Editar ${editando.nome}` : "Novo plano"}</h2></div>
              <button type="button" onClick={fecharModal} aria-label="Fechar"><Icon name="close" /></button>
            </header>
            <form onSubmit={salvar}>
              {erro && <div className="super-admin-alert error">{erro}</div>}
              <div className="super-admin-form-grid two-columns">
                {!editando && (
                  <label>Código<input value={form.codigo} onChange={(e) => setForm({ ...form, codigo: e.target.value.toUpperCase().replace(/\s+/g, "_") })} required /></label>
                )}
                <label>Nome<input value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} required /></label>
                <label className="full">Descrição<textarea rows={3} value={form.descricao} onChange={(e) => setForm({ ...form, descricao: e.target.value })} /></label>
                <label>Preço mensal<input type="number" min="0" step="0.01" value={form.preco} onChange={(e) => setForm({ ...form, preco: e.target.value })} required /></label>
                <label>Preço anual<input type="number" min="0" step="0.01" value={form.preco_anual} onChange={(e) => setForm({ ...form, preco_anual: e.target.value })} placeholder="Opcional" /></label>
                <label>Dias de teste<input type="number" min="0" max="90" value={form.periodo_teste_dias} onChange={(e) => setForm({ ...form, periodo_teste_dias: e.target.value })} required /></label>
                <label>Usuários<input type="number" min="1" value={form.limite_usuarios} onChange={(e) => setForm({ ...form, limite_usuarios: e.target.value })} placeholder="Vazio = ilimitado" /></label>
                <label>Clientes<input type="number" min="1" value={form.limite_clientes} onChange={(e) => setForm({ ...form, limite_clientes: e.target.value })} placeholder="Vazio = ilimitado" /></label>
                <label>Agendamentos/mês<input type="number" min="1" value={form.limite_agendamentos_mes} onChange={(e) => setForm({ ...form, limite_agendamentos_mes: e.target.value })} placeholder="Vazio = ilimitado" /></label>
                <label>Conversas/mês<input type="number" min="1" value={form.limite_conversas_mes} onChange={(e) => setForm({ ...form, limite_conversas_mes: e.target.value })} placeholder="Vazio = ilimitado" /></label>
                <label>Mensagens de IA/mês<input type="number" min="0" value={form.limite_mensagens_ia_mes} onChange={(e) => setForm({ ...form, limite_mensagens_ia_mes: e.target.value })} placeholder="Vazio = ilimitado" /></label>
                <label>Canais<input type="number" min="1" value={form.limite_canais} onChange={(e) => setForm({ ...form, limite_canais: e.target.value })} placeholder="Vazio = ilimitado" /></label>
                <label>Armazenamento (MB)<input type="number" min="1" value={form.limite_armazenamento_mb} onChange={(e) => setForm({ ...form, limite_armazenamento_mb: e.target.value })} placeholder="Vazio = ilimitado" /></label>
              </div>

              <div className="super-admin-toggle-grid">
                <label><input type="checkbox" checked={form.ativo} onChange={(e) => setForm({ ...form, ativo: e.target.checked })} /><span><strong>Plano ativo</strong><small>Disponível para novas empresas</small></span></label>
                <label><input type="checkbox" checked={form.ia_incluida} onChange={(e) => setForm({ ...form, ia_incluida: e.target.checked })} /><span><strong>IA incluída</strong><small>Franquia já faz parte do plano</small></span></label>
                <label><input type="checkbox" checked={form.ia_adicional_disponivel} onChange={(e) => setForm({ ...form, ia_adicional_disponivel: e.target.checked })} /><span><strong>IA como adicional</strong><small>Pode ser contratada separadamente</small></span></label>
              </div>

              <div className="super-admin-resource-section">
                <h3>Recursos liberados</h3>
                <div>
                  {recursosDisponiveis.map(([key, label]) => (
                    <label key={key}>
                      <input type="checkbox" checked={Boolean(form.recursos[key])} onChange={(e) => setForm({ ...form, recursos: { ...form.recursos, [key]: e.target.checked } })} />
                      {label}
                    </label>
                  ))}
                </div>
              </div>

              <footer>
                <button className="super-admin-secondary-button" type="button" onClick={fecharModal} disabled={salvando}>Cancelar</button>
                <button className="super-admin-primary-button" type="submit" disabled={salvando}>{salvando ? "Salvando..." : "Salvar plano"}</button>
              </footer>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
