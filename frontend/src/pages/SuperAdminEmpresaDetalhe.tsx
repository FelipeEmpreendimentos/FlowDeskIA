import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router";
import { Icon } from "../components/Icon";
import { superAdminApiRequest } from "../services/superAdminApi";
import type {
  ConfigIASuperAdmin,
  EmpresaSuperAdminDetalhe,
  PlanoSuperAdmin,
  StatusPlataforma,
} from "../types/superAdmin";
import { formatDate, formatDateTime } from "../utils/format";

const recursos = [
  ["AGENDA", "Agenda"],
  ["CLIENTES", "Clientes"],
  ["VEICULOS", "Veículos"],
  ["SERVICOS", "Serviços"],
  ["CONVERSAS", "Conversas"],
  ["NOTIFICACOES", "Notificações"],
  ["WHATSAPP", "WhatsApp"],
  ["INSTAGRAM", "Instagram"],
  ["INTELIGENCIA_ARTIFICIAL", "Inteligência artificial"],
  ["AVALIACOES", "Avaliações"],
  ["RELATORIOS", "Relatórios"],
  ["AUTOMACOES", "Automações"],
  ["MULTIPLAS_UNIDADES", "Múltiplas unidades"],
  ["SUPORTE_PRIORITARIO", "Suporte prioritário"],
] as const;

const limites = [
  ["usuarios", "Usuários"],
  ["clientes", "Clientes"],
  ["agendamentos_mes", "Agendamentos/mês"],
  ["conversas_mes", "Conversas/mês"],
  ["mensagens_ia_mes", "Mensagens de IA/mês"],
  ["canais", "Canais"],
  ["armazenamento_mb", "Armazenamento (MB)"],
] as const;

const statusLabels: Record<StatusPlataforma, string> = {
  TRIAL: "Em teste",
  ATIVA: "Ativa",
  SUSPENSA: "Suspensa",
  CANCELADA: "Cancelada",
  ARQUIVADA: "Arquivada",
};

type Aba = "geral" | "recursos" | "ia" | "uso";

export function SuperAdminEmpresaDetalhe() {
  const navigate = useNavigate();
  const { empresaId } = useParams();
  const id = Number(empresaId);
  const [aba, setAba] = useState<Aba>("geral");
  const [empresa, setEmpresa] = useState<EmpresaSuperAdminDetalhe | null>(null);
  const [planos, setPlanos] = useState<PlanoSuperAdmin[]>([]);
  const [configIA, setConfigIA] = useState<ConfigIASuperAdmin | null>(null);
  const [planoId, setPlanoId] = useState("");
  const [status, setStatus] = useState<StatusPlataforma>("TRIAL");
  const [trialFim, setTrialFim] = useState("");
  const [iaAdicional, setIaAdicional] = useState(false);
  const [iaLimiteAdicional, setIaLimiteAdicional] = useState("0");
  const [observacoes, setObservacoes] = useState("");
  const [recursosForm, setRecursosForm] = useState<Record<string, boolean>>({});
  const [limitesForm, setLimitesForm] = useState<Record<string, string>>({});
  const [iaNome, setIaNome] = useState("Assistente");
  const [iaBoasVindas, setIaBoasVindas] = useState("");
  const [iaPrompt, setIaPrompt] = useState("");
  const [iaTemperatura, setIaTemperatura] = useState("0.70");
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");

  function preencher(data: EmpresaSuperAdminDetalhe) {
    setEmpresa(data);
    setPlanoId(data.plano_id ? String(data.plano_id) : "");
    setStatus(data.status);
    setTrialFim(data.trial_fim ?? "");
    setIaAdicional(data.ia_adicional_ativo);
    setIaLimiteAdicional(String(data.ia_limite_adicional));
    setObservacoes(data.observacoes ?? "");
    setRecursosForm({ ...data.uso.recursos, ...data.recursos_personalizados });
    setLimitesForm(
      Object.fromEntries(
        limites.map(([key]) => [
          key,
          data.limites_personalizados[key] == null
            ? ""
            : String(data.limites_personalizados[key]),
        ]),
      ),
    );
  }

  async function carregar() {
    if (!Number.isFinite(id)) return;
    setCarregando(true);
    try {
      const [company, plans, ia] = await Promise.all([
        superAdminApiRequest<EmpresaSuperAdminDetalhe>(`/empresas/${id}`),
        superAdminApiRequest<PlanoSuperAdmin[]>("/planos"),
        superAdminApiRequest<ConfigIASuperAdmin | null>(`/empresas/${id}/ia`),
      ]);
      preencher(company);
      setPlanos(plans);
      setConfigIA(ia);
      if (ia) {
        setIaNome(ia.nome_assistente);
        setIaBoasVindas(ia.mensagem_boas_vindas ?? "");
        setIaPrompt(ia.prompt ?? "");
        setIaTemperatura(String(ia.temperatura));
      }
      setErro("");
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível carregar a empresa.");
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    void carregar();
  }, [id]);

  useEffect(() => {
    if (!sucesso) return;
    const timer = window.setTimeout(() => setSucesso(""), 4000);
    return () => window.clearTimeout(timer);
  }, [sucesso]);

  const plano = useMemo(
    () => planos.find((item) => item.id === Number(planoId)) ?? null,
    [planos, planoId],
  );

  async function salvarEmpresa(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSalvando(true);
    setErro("");
    const customLimits = Object.fromEntries(
      Object.entries(limitesForm)
        .filter(([, value]) => value.trim() !== "")
        .map(([key, value]) => [key, Number(value)]),
    );
    try {
      const atualizada = await superAdminApiRequest<EmpresaSuperAdminDetalhe>(
        `/empresas/${id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            plano_id: Number(planoId),
            status,
            trial_fim: trialFim || null,
            recursos_personalizados: recursosForm,
            limites_personalizados: customLimits,
            ia_adicional_ativo: iaAdicional,
            ia_limite_adicional: Number(iaLimiteAdicional || 0),
            observacoes: observacoes.trim() || null,
          }),
        },
      );
      preencher(atualizada);
      setSucesso("Configurações da empresa atualizadas com sucesso.");
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível salvar a empresa.");
    } finally {
      setSalvando(false);
    }
  }

  async function restaurarPadraoPlano() {
    setSalvando(true);
    setErro("");
    try {
      const atualizada = await superAdminApiRequest<EmpresaSuperAdminDetalhe>(
        `/empresas/${id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            recursos_personalizados: {},
            limites_personalizados: {},
          }),
        },
      );
      preencher(atualizada);
      setSucesso("Personalizações removidas. A empresa voltou aos padrões do plano.");
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível restaurar o plano.");
    } finally {
      setSalvando(false);
    }
  }

  async function salvarIA(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSalvando(true);
    setErro("");
    try {
      const data = await superAdminApiRequest<ConfigIASuperAdmin>(
        `/empresas/${id}/ia`,
        {
          method: "PUT",
          body: JSON.stringify({
            nome_assistente: iaNome.trim(),
            mensagem_boas_vindas: iaBoasVindas.trim() || null,
            prompt: iaPrompt.trim() || null,
            temperatura: Number(iaTemperatura),
          }),
        },
      );
      setConfigIA(data);
      setSucesso("Configuração da IA atualizada com sucesso.");
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível salvar a IA.");
    } finally {
      setSalvando(false);
    }
  }

  if (carregando) {
    return <main className="super-admin-state">Carregando empresa...</main>;
  }

  if (!empresa) {
    return (
      <main className="super-admin-page">
        <div className="super-admin-alert error">{erro || "Empresa não encontrada."}</div>
        <button className="super-admin-secondary-button" type="button" onClick={() => navigate("/super-admin/empresas")}>Voltar</button>
      </main>
    );
  }

  return (
    <div className="super-admin-page">
      <header className="super-admin-page-header">
        <div className="super-admin-company-title">
          <button type="button" onClick={() => navigate("/super-admin/empresas")} aria-label="Voltar"><Icon name="arrow-left" /></button>
          <span>{empresa.nome.charAt(0).toUpperCase()}</span>
          <div><small>Empresa #{empresa.id}</small><h1>{empresa.nome}</h1><p>{empresa.cnpj}</p></div>
        </div>
        <span className={`super-admin-status ${empresa.status.toLowerCase()}`}>{statusLabels[empresa.status]}</span>
      </header>

      {sucesso && <div className="super-admin-toast success">{sucesso}</div>}
      {erro && <div className="super-admin-alert error">{erro}</div>}

      <div className="super-admin-tabs">
        <button className={aba === "geral" ? "active" : ""} onClick={() => setAba("geral")}>Geral e assinatura</button>
        <button className={aba === "recursos" ? "active" : ""} onClick={() => setAba("recursos")}>Recursos e limites</button>
        <button className={aba === "ia" ? "active" : ""} onClick={() => setAba("ia")}>Inteligência artificial</button>
        <button className={aba === "uso" ? "active" : ""} onClick={() => setAba("uso")}>Uso atual</button>
      </div>

      {aba === "geral" && (
        <form className="super-admin-card" onSubmit={salvarEmpresa}>
          <div className="super-admin-card-heading"><div><span>Conta empresarial</span><h2>Plano, teste e situação</h2></div><Icon name="building" /></div>
          <div className="super-admin-form-grid two-columns">
            <label>Plano<select value={planoId} onChange={(e) => setPlanoId(e.target.value)} required>{planos.map((item) => <option value={item.id} key={item.id}>{item.nome}{!item.ativo ? " (inativo)" : ""}</option>)}</select></label>
            <label>Status<select value={status} onChange={(e) => setStatus(e.target.value as StatusPlataforma)}><option value="TRIAL">Em teste</option><option value="ATIVA">Ativa</option><option value="SUSPENSA">Suspensa</option><option value="CANCELADA">Cancelada</option><option value="ARQUIVADA">Arquivada</option></select></label>
            <label>Fim do teste<input type="date" value={trialFim} onChange={(e) => setTrialFim(e.target.value)} /></label>
            <label>Plano selecionado<input value={plano?.descricao ?? "Sem descrição"} disabled /></label>
            <label className="full">Observações internas<textarea rows={4} value={observacoes} onChange={(e) => setObservacoes(e.target.value)} placeholder="Condições comerciais, contatos e informações de suporte" /></label>
          </div>
          <div className="super-admin-company-meta"><span>Criada em {formatDateTime(empresa.created_at)}</span><span>Atualizada em {formatDateTime(empresa.updated_at)}</span></div>
          <footer><button className="super-admin-primary-button" type="submit" disabled={salvando}>{salvando ? "Salvando..." : "Salvar empresa"}</button></footer>
        </form>
      )}

      {aba === "recursos" && (
        <form className="super-admin-card" onSubmit={salvarEmpresa}>
          <div className="super-admin-card-heading"><div><span>Feature flags</span><h2>Recursos liberados</h2></div><button className="super-admin-secondary-button" type="button" onClick={() => void restaurarPadraoPlano()} disabled={salvando}>Restaurar padrão</button></div>
          <p className="super-admin-section-copy">As opções abaixo substituem o padrão do plano somente para esta empresa.</p>
          <div className="super-admin-feature-grid">
            {recursos.map(([key, label]) => (
              <label key={key}>
                <input type="checkbox" checked={Boolean(recursosForm[key])} onChange={(e) => setRecursosForm({ ...recursosForm, [key]: e.target.checked })} />
                <span><strong>{label}</strong><small>{recursosForm[key] ? "Liberado" : "Bloqueado"}</small></span>
              </label>
            ))}
          </div>

          <div className="super-admin-card-heading separated"><div><span>Franquias</span><h2>Limites personalizados</h2></div></div>
          <div className="super-admin-form-grid two-columns">
            {limites.map(([key, label]) => (
              <label key={key}>{label}<input type="number" min="0" value={limitesForm[key] ?? ""} onChange={(e) => setLimitesForm({ ...limitesForm, [key]: e.target.value })} placeholder={`Padrão: ${empresa.uso.limites[key] ?? "ilimitado"}`} /></label>
            ))}
          </div>

          <div className="super-admin-card-heading separated"><div><span>Adicional comercial</span><h2>Inteligência artificial</h2></div></div>
          <div className="super-admin-toggle-grid">
            <label><input type="checkbox" checked={iaAdicional} onChange={(e) => setIaAdicional(e.target.checked)} /><span><strong>IA adicional ativa</strong><small>Disponível até no plano Essencial</small></span></label>
            <label><span><strong>Franquia adicional</strong><input type="number" min="0" value={iaLimiteAdicional} onChange={(e) => setIaLimiteAdicional(e.target.value)} /></span></label>
          </div>
          <footer><button className="super-admin-primary-button" type="submit" disabled={salvando}>{salvando ? "Salvando..." : "Salvar recursos"}</button></footer>
        </form>
      )}

      {aba === "ia" && (
        <form className="super-admin-card" onSubmit={salvarIA}>
          <div className="super-admin-card-heading"><div><span>Controle proprietário</span><h2>Configuração da IA</h2></div><Icon name="bot" /></div>
          {!empresa.uso.recursos.INTELIGENCIA_ARTIFICIAL && <div className="super-admin-alert info">A IA está configurável, mas permanece bloqueada até ser incluída no plano ou ativada como adicional.</div>}
          <div className="super-admin-form-grid">
            <label>Nome do assistente<input value={iaNome} onChange={(e) => setIaNome(e.target.value)} required /></label>
            <label>Mensagem de boas-vindas<textarea rows={3} value={iaBoasVindas} onChange={(e) => setIaBoasVindas(e.target.value)} /></label>
            <label>Prompt de sistema<textarea rows={10} value={iaPrompt} onChange={(e) => setIaPrompt(e.target.value)} placeholder="Regras, linguagem, serviços e critérios de transferência para humanos." /></label>
            <label>Temperatura: {Number(iaTemperatura).toFixed(1)}<input type="range" min="0" max="2" step="0.1" value={iaTemperatura} onChange={(e) => setIaTemperatura(e.target.value)} /></label>
          </div>
          <p className="super-admin-section-copy">Última configuração carregada: {configIA ? `registro #${configIA.id}` : "ainda não criada"}.</p>
          <footer><button className="super-admin-primary-button" type="submit" disabled={salvando}>{salvando ? "Salvando..." : "Salvar configuração da IA"}</button></footer>
        </form>
      )}

      {aba === "uso" && (
        <section className="super-admin-card">
          <div className="super-admin-card-heading"><div><span>Competência atual</span><h2>Uso e limites</h2></div><Icon name="dashboard" /></div>
          <div className="super-admin-usage-grid">
            <article><span>Usuários</span><strong>{empresa.uso.usuarios_ativos}</strong><small>Limite {empresa.uso.limites.usuarios ?? "ilimitado"}</small></article>
            <article><span>Clientes</span><strong>{empresa.uso.clientes}</strong><small>Limite {empresa.uso.limites.clientes ?? "ilimitado"}</small></article>
            <article><span>Agendamentos</span><strong>{empresa.uso.agendamentos_mes}</strong><small>Limite {empresa.uso.limites.agendamentos_mes ?? "ilimitado"}</small></article>
            <article><span>Conversas</span><strong>{empresa.uso.conversas_mes}</strong><small>Limite {empresa.uso.limites.conversas_mes ?? "ilimitado"}</small></article>
            <article><span>Mensagens de IA</span><strong>{empresa.uso.mensagens_ia_mes}</strong><small>Limite {empresa.uso.limites.mensagens_ia_mes ?? "ilimitado"}</small></article>
            <article><span>Canais</span><strong>{empresa.uso.canais_ativos}</strong><small>Limite {empresa.uso.limites.canais ?? "ilimitado"}</small></article>
          </div>
          <div className="super-admin-company-meta"><span>Teste: {empresa.trial_fim ? `até ${formatDate(empresa.trial_fim)}` : "não definido"}</span><span>Plano: {empresa.plano_nome ?? "sem plano"}</span></div>
        </section>
      )}
    </div>
  );
}
