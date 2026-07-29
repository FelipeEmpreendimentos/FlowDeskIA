import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router";
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
import type { Cliente, StatusCliente } from "../types";
import { normalizeNullable } from "../utils/format";

type CampoBuscaCliente = "todos" | "nome" | "telefone" | "email";

interface ClienteForm {
  nome: string;
  whatsapp: string;
  email: string;
  observacoes: string;
  status: StatusCliente;
}

interface ResumoClientes {
  resultados: number;
  ativos: number;
  inativos: number;
  bloqueados: number;
}

const formVazio: ClienteForm = {
  nome: "",
  whatsapp: "",
  email: "",
  observacoes: "",
  status: "ATIVO",
};

const resumoVazio: ResumoClientes = {
  resultados: 0,
  ativos: 0,
  inativos: 0,
  bloqueados: 0,
};

const placeholdersBusca: Record<CampoBuscaCliente, string> = {
  todos: "Buscar por nome, WhatsApp ou e-mail",
  nome: "Buscar por nome",
  telefone: "Buscar por WhatsApp",
  email: "Buscar por e-mail",
};

export function Clientes() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [resumo, setResumo] = useState<ResumoClientes>(resumoVazio);
  const [busca, setBusca] = useState("");
  const [campoBusca, setCampoBusca] = useState<CampoBuscaCliente>("todos");
  const [status, setStatus] = useState<StatusCliente | "">("ATIVO");
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");
  const [modalAberto, setModalAberto] = useState(
    searchParams.get("novo") === "1",
  );
  const [editando, setEditando] = useState<Cliente | null>(null);
  const [form, setForm] = useState<ClienteForm>({ ...formVazio });
  const [clienteConfirmacao, setClienteConfirmacao] =
    useState<Cliente | null>(null);
  const [alterandoSituacao, setAlterandoSituacao] = useState(false);
  const [erroConfirmacao, setErroConfirmacao] = useState("");

  async function carregarClientes() {
    setCarregando(true);
    setErro("");

    try {
      const data = await apiRequest<Cliente[]>(
        `/clientes${buildQuery({
          busca,
          campo_busca: campoBusca,
          status_cliente: status,
          limit: 100,
        })}`,
      );
      setClientes(data);
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível carregar os clientes.",
      );
    } finally {
      setCarregando(false);
    }
  }

  async function carregarResumoClientes() {
    try {
      const data = await apiRequest<Cliente[]>("/clientes?limit=200");

      setResumo({
        resultados: data.length,
        ativos: data.filter((item) => item.status === "ATIVO").length,
        inativos: data.filter((item) => item.status === "INATIVO").length,
        bloqueados: data.filter((item) => item.status === "BLOQUEADO").length,
      });
    } catch {
      // O resumo é complementar. A listagem principal continua funcionando.
    }
  }

  useEffect(() => {
    void carregarResumoClientes();
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void carregarClientes();
    }, 250);

    return () => window.clearTimeout(timer);
  }, [busca, campoBusca, status]);

  useEffect(() => {
    if (!sucesso) return;

    const timer = window.setTimeout(() => {
      setSucesso("");
    }, 4000);

    return () => window.clearTimeout(timer);
  }, [sucesso]);

  useEffect(() => {
    if (searchParams.get("novo") === "1") {
      abrirNovo();
      setSearchParams({}, { replace: true });
    }
  }, []);

  function alterarCampoBusca(novoCampo: CampoBuscaCliente) {
    setCampoBusca(novoCampo);
    setBusca("");
  }

  function abrirNovo() {
    setEditando(null);
    setForm({ ...formVazio });
    setModalAberto(true);
    setErro("");
  }

  function abrirEdicao(cliente: Cliente) {
    setEditando(cliente);
    setForm({
      nome: cliente.nome,
      whatsapp: cliente.whatsapp ?? cliente.telefone ?? "",
      email: cliente.email ?? "",
      observacoes: cliente.observacoes ?? "",
      status: cliente.status,
    });
    setModalAberto(true);
    setErro("");
  }

  function fecharModal() {
    setModalAberto(false);
    setEditando(null);
    setForm({ ...formVazio });
    setErro("");
  }

  async function salvar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSalvando(true);
    setErro("");

    const payload = {
      nome: form.nome.trim(),
      whatsapp: normalizeNullable(form.whatsapp),
      email: normalizeNullable(form.email),
      observacoes: normalizeNullable(form.observacoes),
      ...(editando ? { status: form.status } : {}),
    };

    try {
      if (editando) {
        await apiRequest<Cliente>(`/clientes/${editando.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        setSucesso("Cliente atualizado com sucesso.");
      } else {
        await apiRequest<Cliente>("/clientes", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setSucesso("Cliente cadastrado com sucesso.");
      }

      fecharModal();
      await Promise.all([carregarClientes(), carregarResumoClientes()]);
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível salvar o cliente.",
      );
    } finally {
      setSalvando(false);
    }
  }

  function abrirConfirmacaoSituacao(cliente: Cliente) {
    setClienteConfirmacao(cliente);
    setErroConfirmacao("");
  }

  function fecharConfirmacaoSituacao() {
    if (alterandoSituacao) return;
    setClienteConfirmacao(null);
    setErroConfirmacao("");
  }

  async function confirmarAlteracaoSituacao() {
    if (!clienteConfirmacao) return;

    const ativar = clienteConfirmacao.status !== "ATIVO";
    setAlterandoSituacao(true);
    setErroConfirmacao("");

    try {
      if (ativar) {
        await apiRequest<Cliente>(`/clientes/${clienteConfirmacao.id}`, {
          method: "PATCH",
          body: JSON.stringify({ status: "ATIVO" }),
        });
        setSucesso("Cliente reativado com sucesso.");
      } else {
        await apiRequest<void>(`/clientes/${clienteConfirmacao.id}`, {
          method: "DELETE",
        });
        setSucesso("Cliente desativado com sucesso.");
      }

      setClienteConfirmacao(null);
      await Promise.all([carregarClientes(), carregarResumoClientes()]);
    } catch (error) {
      setErroConfirmacao(
        error instanceof Error
          ? error.message
          : "Não foi possível alterar a situação do cliente.",
      );
    } finally {
      setAlterandoSituacao(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Relacionamento"
        title="Clientes"
        description="Cadastre, pesquise e acompanhe sua base de clientes."
        actions={
          <button
            className="button button-primary"
            type="button"
            onClick={abrirNovo}
          >
            <Icon name="plus" size={18} />
            Novo cliente
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

      {erro && !modalAberto && !clienteConfirmacao && <Alert>{erro}</Alert>}

      <section className="mini-metrics">
        <article>
          <strong>{resumo.resultados}</strong>
          <span>Resultados</span>
        </article>
        <article>
          <strong>{resumo.ativos}</strong>
          <span>Ativos</span>
        </article>
        <article>
          <strong>{resumo.inativos}</strong>
          <span>Inativos</span>
        </article>
        <article>
          <strong>{resumo.bloqueados}</strong>
          <span>Bloqueados</span>
        </article>
      </section>

      <section className="content-card">
        <div className="toolbar">
          <div className="toolbar-search-group">
            <label className="search-field">
              <Icon name="search" size={18} />
              <input
                value={busca}
                onChange={(event) => setBusca(event.target.value)}
                placeholder={placeholdersBusca[campoBusca]}
                aria-label={placeholdersBusca[campoBusca]}
              />
            </label>

            <label className="search-filter" title="Escolher campo da busca">
              <Icon name="filter" size={17} />
              <select
                value={campoBusca}
                onChange={(event) =>
                  alterarCampoBusca(event.target.value as CampoBuscaCliente)
                }
                aria-label="Filtrar busca de clientes por campo"
              >
                <option value="todos">Todos os campos</option>
                <option value="nome">Nome</option>
                <option value="telefone">WhatsApp</option>
                <option value="email">E-mail</option>
              </select>
            </label>
          </div>

          <select
            value={status}
            onChange={(event) =>
              setStatus(event.target.value as StatusCliente | "")
            }
            aria-label="Filtrar clientes por status"
          >
            <option value="">Todos os status</option>
            <option value="ATIVO">Ativos</option>
            <option value="INATIVO">Inativos</option>
            <option value="BLOQUEADO">Bloqueados</option>
          </select>
        </div>

        {carregando ? (
          <LoadingState label="Carregando clientes..." />
        ) : clientes.length === 0 ? (
          <EmptyState
            icon="users"
            title="Nenhum cliente encontrado"
            description="Altere os filtros ou cadastre o primeiro cliente."
            action={
              <button
                className="button button-primary"
                type="button"
                onClick={abrirNovo}
              >
                Cadastrar cliente
              </button>
            }
          />
        ) : (
          <div className="table-wrap">
            <table className="data-table client-table">
              <thead>
                <tr>
                  <th>Cliente</th>
                  <th>WhatsApp</th>
                  <th>E-mail</th>
                  <th>Status</th>
                  <th className="actions-column">Ações</th>
                </tr>
              </thead>
              <tbody>
                {clientes.map((cliente) => (
                  <tr key={cliente.id}>
                    <td>
                      <div className="entity-cell">
                        <span className="entity-avatar">
                          {cliente.nome.charAt(0).toUpperCase()}
                        </span>
                        <div>
                          <strong>{cliente.nome}</strong>
                          <small>Cliente #{cliente.id}</small>
                        </div>
                      </div>
                    </td>
                    <td>
                      <strong className="table-primary">
                        {cliente.whatsapp ?? cliente.telefone ?? "—"}
                      </strong>
                      <small>
                        {cliente.whatsapp || cliente.telefone
                          ? "WhatsApp"
                          : "Sem WhatsApp"}
                      </small>
                    </td>
                    <td>{cliente.email ?? "Sem e-mail"}</td>
                    <td>
                      <StatusBadge value={cliente.status} />
                    </td>
                    <td>
                      <div className="row-actions">
                        <button
                          className="icon-button"
                          type="button"
                          onClick={() =>
                            navigate(`/veiculos?cliente=${cliente.id}`)
                          }
                          title="Ver veículos"
                        >
                          <Icon name="car" size={17} />
                        </button>
                        <button
                          className="icon-button"
                          type="button"
                          onClick={() => abrirEdicao(cliente)}
                          title="Editar"
                        >
                          <Icon name="edit" size={17} />
                        </button>
                        <button
                          className={`icon-button ${
                            cliente.status === "ATIVO" ? "danger" : "success"
                          }`}
                          type="button"
                          onClick={() => abrirConfirmacaoSituacao(cliente)}
                          title={
                            cliente.status === "ATIVO"
                              ? "Desativar"
                              : "Reativar"
                          }
                        >
                          <Icon
                            name={
                              cliente.status === "ATIVO"
                                ? "pause"
                                : "refresh"
                            }
                            size={17}
                          />
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
        open={modalAberto}
        title={editando ? "Editar cliente" : "Novo cliente"}
        subtitle="Informe os dados essenciais do cliente."
        onClose={fecharModal}
        size="large"
      >
        <form onSubmit={salvar}>
          {erro && <Alert>{erro}</Alert>}

          <div className="form-grid form-grid-2">
            <label className="field field-span-2">
              Nome completo
              <input
                value={form.nome}
                onChange={(event) =>
                  setForm({ ...form, nome: event.target.value })
                }
                required
                minLength={2}
                autoComplete="name"
              />
            </label>

            <label className="field">
              WhatsApp
              <input
                value={form.whatsapp}
                onChange={(event) =>
                  setForm({ ...form, whatsapp: event.target.value })
                }
                placeholder="(46) 99999-9999"
                inputMode="tel"
                autoComplete="tel"
                required
              />
            </label>

            <label className="field">
              E-mail
              <input
                type="email"
                value={form.email}
                onChange={(event) =>
                  setForm({ ...form, email: event.target.value })
                }
                placeholder="cliente@exemplo.com"
                autoComplete="email"
              />
            </label>

            {editando && (
              <label className="field field-span-2">
                Status
                <select
                  value={form.status}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      status: event.target.value as StatusCliente,
                    })
                  }
                >
                  <option value="ATIVO">Ativo</option>
                  <option value="INATIVO">Inativo</option>
                  <option value="BLOQUEADO">Bloqueado</option>
                </select>
              </label>
            )}

            <label className="field field-span-2">
              Observações
              <textarea
                rows={4}
                value={form.observacoes}
                onChange={(event) =>
                  setForm({ ...form, observacoes: event.target.value })
                }
                placeholder="Informações importantes sobre o cliente"
              />
            </label>
          </div>

          <div className="modal-actions">
            <button
              className="button button-secondary"
              type="button"
              onClick={fecharModal}
            >
              Cancelar
            </button>
            <button
              className="button button-primary"
              type="submit"
              disabled={salvando}
            >
              {salvando
                ? "Salvando..."
                : editando
                  ? "Salvar alterações"
                  : "Cadastrar cliente"}
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        open={Boolean(clienteConfirmacao)}
        title={
          clienteConfirmacao?.status === "ATIVO"
            ? "Desativar cliente"
            : "Reativar cliente"
        }
        subtitle="Confirme a alteração antes de continuar."
        onClose={fecharConfirmacaoSituacao}
        size="small"
      >
        {clienteConfirmacao && (
          <div className="confirmation-dialog">
            <span
              className={`confirmation-icon ${
                clienteConfirmacao.status === "ATIVO"
                  ? "confirmation-icon-danger"
                  : "confirmation-icon-success"
              }`}
            >
              <Icon
                name={
                  clienteConfirmacao.status === "ATIVO" ? "pause" : "refresh"
                }
                size={24}
              />
            </span>

            <div className="confirmation-copy">
              <strong>
                {clienteConfirmacao.status === "ATIVO"
                  ? `Desativar ${clienteConfirmacao.nome}?`
                  : `Reativar ${clienteConfirmacao.nome}?`}
              </strong>
              <p>
                {clienteConfirmacao.status === "ATIVO"
                  ? "O cliente será movido para a lista de inativos e poderá ser reativado posteriormente."
                  : "O cliente voltará a aparecer como ativo e poderá receber novos atendimentos."}
              </p>
            </div>

            {erroConfirmacao && <Alert>{erroConfirmacao}</Alert>}

            <div className="modal-actions confirmation-actions">
              <button
                className="button button-secondary"
                type="button"
                onClick={fecharConfirmacaoSituacao}
                disabled={alterandoSituacao}
              >
                Cancelar
              </button>
              <button
                className={
                  clienteConfirmacao.status === "ATIVO"
                    ? "button button-danger"
                    : "button button-primary"
                }
                type="button"
                onClick={() => void confirmarAlteracaoSituacao()}
                disabled={alterandoSituacao}
              >
                {alterandoSituacao
                  ? "Processando..."
                  : clienteConfirmacao.status === "ATIVO"
                    ? "Desativar cliente"
                    : "Reativar cliente"}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
