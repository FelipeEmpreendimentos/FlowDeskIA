import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { Icon } from "../components/Icon";
import {
  superAdminApiRequest,
  superAdminBuildQuery,
} from "../services/superAdminApi";
import type {
  EmpresaSuperAdminDetalhe,
  EmpresaSuperAdminResumo,
  PlanoSuperAdmin,
  StatusPlataforma,
} from "../types/superAdmin";
import { formatDate } from "../utils/format";

interface EmpresaForm {
  nome: string;
  cnpj: string;
  telefone: string;
  email: string;
  cidade: string;
  estado: string;
  timezone: string;
  plano_id: string;
  periodo_teste_dias: string;
  admin_nome: string;
  admin_email: string;
  admin_senha: string;
}

const formVazio: EmpresaForm = {
  nome: "",
  cnpj: "",
  telefone: "",
  email: "",
  cidade: "",
  estado: "",
  timezone: "America/Sao_Paulo",
  plano_id: "",
  periodo_teste_dias: "14",
  admin_nome: "",
  admin_email: "",
  admin_senha: "",
};

const statusLabels: Record<StatusPlataforma, string> = {
  TRIAL: "Em teste",
  ATIVA: "Ativa",
  SUSPENSA: "Suspensa",
  CANCELADA: "Cancelada",
  ARQUIVADA: "Arquivada",
};

export function SuperAdminEmpresas() {
  const [empresas, setEmpresas] = useState<EmpresaSuperAdminResumo[]>([]);
  const [planos, setPlanos] = useState<PlanoSuperAdmin[]>([]);
  const [busca, setBusca] = useState("");
  const [statusFiltro, setStatusFiltro] = useState("");
  const [planoFiltro, setPlanoFiltro] = useState("");
  const [modalAberto, setModalAberto] = useState(false);
  const [form, setForm] = useState<EmpresaForm>({ ...formVazio });
  const [mostrarSenha, setMostrarSenha] = useState(false);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");

  async function carregarPlanos() {
    const data = await superAdminApiRequest<PlanoSuperAdmin[]>(
      "/planos?somente_ativos=true",
    );
    setPlanos(data);
    if (!form.plano_id && data[0]) {
      setForm((current) => ({ ...current, plano_id: String(data[0].id) }));
    }
  }

  async function carregarEmpresas() {
    setCarregando(true);
    try {
      const data = await superAdminApiRequest<EmpresaSuperAdminResumo[]>(
        `/empresas${superAdminBuildQuery({
          busca,
          status_empresa: statusFiltro,
          plano_id: planoFiltro,
        })}`,
      );
      setEmpresas(data);
      setErro("");
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível carregar as empresas.");
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    void carregarPlanos();
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void carregarEmpresas(), 250);
    return () => window.clearTimeout(timer);
  }, [busca, statusFiltro, planoFiltro]);

  useEffect(() => {
    if (!sucesso) return;
    const timer = window.setTimeout(() => setSucesso(""), 4000);
    return () => window.clearTimeout(timer);
  }, [sucesso]);

  function abrirNovaEmpresa() {
    setForm({
      ...formVazio,
      plano_id: planos[0] ? String(planos[0].id) : "",
    });
    setErro("");
    setModalAberto(true);
  }

  function fecharModal() {
    if (salvando) return;
    setModalAberto(false);
    setErro("");
    setMostrarSenha(false);
  }

  async function criarEmpresa(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSalvando(true);
    setErro("");
    try {
      await superAdminApiRequest<EmpresaSuperAdminDetalhe>("/empresas", {
        method: "POST",
        body: JSON.stringify({
          nome: form.nome.trim(),
          cnpj: form.cnpj.trim(),
          telefone: form.telefone.trim() || null,
          email: form.email.trim() || null,
          cidade: form.cidade.trim() || null,
          estado: form.estado.trim().toUpperCase() || null,
          timezone: form.timezone,
          plano_id: Number(form.plano_id),
          periodo_teste_dias: Number(form.periodo_teste_dias),
          admin_nome: form.admin_nome.trim(),
          admin_email: form.admin_email.trim(),
          admin_senha: form.admin_senha,
        }),
      });
      setModalAberto(false);
      setSucesso("Empresa e primeiro administrador criados com sucesso.");
      await carregarEmpresas();
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível criar a empresa.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="super-admin-page">
      <header className="super-admin-page-header">
        <div>
          <span>Clientes da plataforma</span>
          <h1>Empresas</h1>
          <p>Controle plano, teste, IA, limites e situação de cada empresa.</p>
        </div>
        <button className="super-admin-primary-button" type="button" onClick={abrirNovaEmpresa}>
          <Icon name="plus" size={18} />
          Nova empresa
        </button>
      </header>

      {sucesso && <div className="super-admin-toast success">{sucesso}</div>}
      {erro && !modalAberto && <div className="super-admin-alert error">{erro}</div>}

      <section className="super-admin-card super-admin-company-toolbar">
        <label>
          <Icon name="search" size={18} />
          <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar por nome, CNPJ ou e-mail" />
        </label>
        <select value={statusFiltro} onChange={(e) => setStatusFiltro(e.target.value)}>
          <option value="">Todos os status</option>
          <option value="TRIAL">Em teste</option>
          <option value="ATIVA">Ativas</option>
          <option value="SUSPENSA">Suspensas</option>
          <option value="CANCELADA">Canceladas</option>
          <option value="ARQUIVADA">Arquivadas</option>
        </select>
        <select value={planoFiltro} onChange={(e) => setPlanoFiltro(e.target.value)}>
          <option value="">Todos os planos</option>
          {planos.map((plan) => <option value={plan.id} key={plan.id}>{plan.nome}</option>)}
        </select>
      </section>

      {carregando ? (
        <div className="super-admin-state">Carregando empresas...</div>
      ) : empresas.length === 0 ? (
        <div className="super-admin-state">Nenhuma empresa encontrada.</div>
      ) : (
        <section className="super-admin-card super-admin-table-wrap">
          <table className="super-admin-table">
            <thead>
              <tr>
                <th>Empresa</th>
                <th>Plano</th>
                <th>Status</th>
                <th>Teste até</th>
                <th>Uso</th>
                <th>IA</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {empresas.map((empresa) => (
                <tr key={empresa.id}>
                  <td>
                    <div className="super-admin-company-cell">
                      <span>{empresa.nome.charAt(0).toUpperCase()}</span>
                      <div><strong>{empresa.nome}</strong><small>{empresa.cnpj}</small></div>
                    </div>
                  </td>
                  <td>{empresa.plano_nome ?? "Sem plano"}</td>
                  <td><span className={`super-admin-status ${empresa.status.toLowerCase()}`}>{statusLabels[empresa.status]}</span></td>
                  <td>{empresa.trial_fim ? formatDate(empresa.trial_fim) : "—"}</td>
                  <td>
                    <strong>{empresa.usuarios_ativos} usuários</strong>
                    <small>{empresa.agendamentos_mes} agendamentos no mês</small>
                  </td>
                  <td>{empresa.ia_adicional_ativo ? "Adicional ativo" : "Conforme o plano"}</td>
                  <td><Link className="super-admin-row-link" to={`/super-admin/empresas/${empresa.id}`}>Abrir</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {modalAberto && (
        <div className="super-admin-modal-backdrop">
          <section className="super-admin-modal large" role="dialog" aria-modal="true">
            <header>
              <div><span>Nova conta empresarial</span><h2>Cadastrar empresa</h2></div>
              <button type="button" onClick={fecharModal} aria-label="Fechar"><Icon name="close" /></button>
            </header>
            <form onSubmit={criarEmpresa}>
              {erro && <div className="super-admin-alert error">{erro}</div>}
              <h3>Dados da empresa</h3>
              <div className="super-admin-form-grid two-columns">
                <label>Nome da empresa<input value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} required /></label>
                <label>CNPJ<input value={form.cnpj} onChange={(e) => setForm({ ...form, cnpj: e.target.value })} required /></label>
                <label>Telefone<input value={form.telefone} onChange={(e) => setForm({ ...form, telefone: e.target.value })} /></label>
                <label>E-mail da empresa<input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
                <label>Cidade<input value={form.cidade} onChange={(e) => setForm({ ...form, cidade: e.target.value })} /></label>
                <label>Estado<input maxLength={2} value={form.estado} onChange={(e) => setForm({ ...form, estado: e.target.value.toUpperCase() })} /></label>
                <label>Plano<select value={form.plano_id} onChange={(e) => setForm({ ...form, plano_id: e.target.value })} required>{planos.map((plan) => <option value={plan.id} key={plan.id}>{plan.nome}</option>)}</select></label>
                <label>Período de teste<input type="number" min="0" max="90" value={form.periodo_teste_dias} onChange={(e) => setForm({ ...form, periodo_teste_dias: e.target.value })} required /></label>
              </div>

              <h3>Primeiro administrador</h3>
              <div className="super-admin-form-grid two-columns">
                <label>Nome<input value={form.admin_nome} onChange={(e) => setForm({ ...form, admin_nome: e.target.value })} required /></label>
                <label>E-mail de acesso<input type="email" value={form.admin_email} onChange={(e) => setForm({ ...form, admin_email: e.target.value })} required /></label>
                <label className="full">Senha inicial<div className="super-admin-password-field"><input type={mostrarSenha ? "text" : "password"} minLength={8} value={form.admin_senha} onChange={(e) => setForm({ ...form, admin_senha: e.target.value })} required /><button type="button" onClick={() => setMostrarSenha((value) => !value)}><Icon name="eye" size={18} /></button></div></label>
              </div>

              <footer>
                <button className="super-admin-secondary-button" type="button" onClick={fecharModal} disabled={salvando}>Cancelar</button>
                <button className="super-admin-primary-button" type="submit" disabled={salvando}>{salvando ? "Criando..." : "Criar empresa"}</button>
              </footer>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
