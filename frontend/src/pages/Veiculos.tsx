import { useEffect, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";
import { ConfirmationModal } from "../components/ConfirmationModal";
import { Icon } from "../components/Icon";
import { Modal } from "../components/Modal";
import { Alert, EmptyState, LoadingState, PageHeader } from "../components/UI";
import { apiRequest, buildQuery } from "../services/api";
import { showAppToast } from "../services/feedback";
import type { Cliente, TipoVeiculo, Veiculo } from "../types";
import { displayVehicle, normalizeNullable } from "../utils/format";

type CampoBuscaVeiculo =
  | "todos"
  | "cliente"
  | "modelo"
  | "apelido"
  | "tipo";

interface VeiculoForm {
  cliente_id: string;
  tipo_veiculo: TipoVeiculo | "";
  modelo: string;
  apelido: string;
  observacoes: string;
}

const formVazio: VeiculoForm = {
  cliente_id: "",
  tipo_veiculo: "",
  modelo: "",
  apelido: "",
  observacoes: "",
};

const placeholdersBusca: Record<CampoBuscaVeiculo, string> = {
  todos: "Buscar por cliente, modelo, apelido ou tipo",
  cliente: "Buscar por cliente",
  modelo: "Buscar por modelo",
  apelido: "Buscar por apelido",
  tipo: "Buscar por tipo de veículo",
};

const tiposVeiculo: Array<{ value: TipoVeiculo; label: string }> = [
  { value: "HATCH", label: "Hatch" },
  { value: "SEDAN", label: "Sedã" },
  { value: "SUV", label: "SUV" },
  { value: "CAMINHONETE", label: "Caminhonete" },
  { value: "OUTRO", label: "Outro" },
];

function tipoVeiculoLabel(tipo: TipoVeiculo | null): string {
  return (
    tiposVeiculo.find((item) => item.value === tipo)?.label ??
    "Não informado"
  );
}

export function Veiculos() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [clienteInicial] = useState(() => searchParams.get("cliente") ?? "");
  const clienteInicialAplicado = useRef(false);
  const [veiculos, setVeiculos] = useState<Veiculo[]>([]);
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [busca, setBusca] = useState("");
  const [campoBusca, setCampoBusca] = useState<CampoBuscaVeiculo>("todos");
  const [carregando, setCarregando] = useState(true);
  const [modalAberto, setModalAberto] = useState(false);
  const [editando, setEditando] = useState<Veiculo | null>(null);
  const [form, setForm] = useState<VeiculoForm>({
    ...formVazio,
    cliente_id: clienteInicial,
  });
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [veiculoExclusao, setVeiculoExclusao] = useState<Veiculo | null>(null);
  const [excluindo, setExcluindo] = useState(false);

  async function carregar() {
    setCarregando(true);
    setErro("");

    try {
      const [dadosVeiculos, dadosClientes] = await Promise.all([
        apiRequest<Veiculo[]>(
          `/veiculos${buildQuery({
            busca,
            campo_busca: campoBusca,
            limit: 100,
          })}`,
        ),
        apiRequest<Cliente[]>("/clientes?limit=100"),
      ]);

      setVeiculos(dadosVeiculos);
      setClientes(dadosClientes);
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível carregar os veículos.",
      );
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void carregar();
    }, 250);

    return () => window.clearTimeout(timer);
  }, [busca, campoBusca]);

  const clienteNome = (id: number) =>
    clientes.find((item) => item.id === id)?.nome ?? `Cliente #${id}`;

  useEffect(() => {
    if (
      clienteInicialAplicado.current ||
      !clienteInicial ||
      clientes.length === 0
    ) {
      return;
    }

    clienteInicialAplicado.current = true;
    const cliente = clientes.find((item) => item.id === Number(clienteInicial));

    if (cliente) {
      setCampoBusca("cliente");
      setBusca(cliente.nome);
    }

    setSearchParams({}, { replace: true });
  }, [clienteInicial, clientes, setSearchParams]);

  function alterarCampoBusca(novoCampo: CampoBuscaVeiculo) {
    setCampoBusca(novoCampo);
    setBusca("");
  }

  function abrirNovo() {
    setEditando(null);
    setForm({
      ...formVazio,
      cliente_id: clienteInicial || "",
    });
    setModalAberto(true);
    setErro("");
  }

  function abrirEdicao(item: Veiculo) {
    setEditando(item);
    setForm({
      cliente_id: item.cliente_id.toString(),
      tipo_veiculo: item.tipo_veiculo ?? "",
      modelo: item.modelo ?? "",
      apelido: item.apelido ?? "",
      observacoes: item.observacoes ?? "",
    });
    setModalAberto(true);
    setErro("");
  }

  function fecharModal() {
    setModalAberto(false);
    setEditando(null);
    setForm({
      ...formVazio,
      cliente_id: clienteInicial || "",
    });
  }

  async function salvar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSalvando(true);
    setErro("");

    const fields = {
      tipo_veiculo: form.tipo_veiculo || null,
      modelo: normalizeNullable(form.modelo),
      apelido: normalizeNullable(form.apelido),
      observacoes: normalizeNullable(form.observacoes),
    };

    try {
      if (editando) {
        await apiRequest<Veiculo>(`/veiculos/${editando.id}`, {
          method: "PATCH",
          body: JSON.stringify(fields),
        });
        showAppToast("Veículo atualizado com sucesso.");
      } else {
        await apiRequest<Veiculo>("/veiculos", {
          method: "POST",
          body: JSON.stringify({
            cliente_id: Number(form.cliente_id),
            ...fields,
          }),
        });
        showAppToast("Veículo cadastrado com sucesso.");
      }

      fecharModal();
      await carregar();
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível salvar o veículo.",
      );
    } finally {
      setSalvando(false);
    }
  }

  function solicitarExclusao(item: Veiculo) {
    setErro("");
    setVeiculoExclusao(item);
  }

  function fecharExclusao() {
    if (excluindo) return;
    setVeiculoExclusao(null);
    setErro("");
  }

  async function confirmarExclusao() {
    if (!veiculoExclusao) return;

    setExcluindo(true);
    setErro("");
    try {
      await apiRequest<void>(`/veiculos/${veiculoExclusao.id}`, {
        method: "DELETE",
      });
      setVeiculoExclusao(null);
      showAppToast("Veículo excluído com sucesso.");
      await carregar();
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível excluir o veículo.",
      );
    } finally {
      setExcluindo(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Cadastro automotivo"
        title="Veículos"
        description="Gerencie os veículos vinculados aos seus clientes."
        actions={
          <button
            className="button button-primary"
            type="button"
            onClick={abrirNovo}
          >
            <Icon name="plus" size={18} />
            Novo veículo
          </button>
        }
      />

      {erro && !modalAberto && !veiculoExclusao && <Alert>{erro}</Alert>}

      <section className="content-card">
        <div className="toolbar">
          <div className="toolbar-search-group">
            <label className="search-field">
              <Icon name="search" size={18} />
              {campoBusca === "tipo" ? (
                <select
                  value={busca}
                  onChange={(event) => setBusca(event.target.value)}
                  aria-label="Selecionar tipo de veículo para busca"
                >
                  <option value="">Selecione o tipo</option>
                  {tiposVeiculo.map((tipo) => (
                    <option key={tipo.value} value={tipo.value}>
                      {tipo.label}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  value={busca}
                  onChange={(event) => setBusca(event.target.value)}
                  placeholder={placeholdersBusca[campoBusca]}
                  aria-label={placeholdersBusca[campoBusca]}
                />
              )}
            </label>

            <label className="search-filter" title="Escolher campo da busca">
              <Icon name="filter" size={17} />
              <select
                value={campoBusca}
                onChange={(event) =>
                  alterarCampoBusca(event.target.value as CampoBuscaVeiculo)
                }
                aria-label="Filtrar busca de veículos por campo"
              >
                <option value="todos">Todos os campos</option>
                <option value="cliente">Cliente</option>
                <option value="modelo">Modelo</option>
                <option value="apelido">Apelido</option>
                <option value="tipo">Tipo</option>
              </select>
            </label>
          </div>
        </div>

        {carregando ? (
          <LoadingState label="Carregando veículos..." />
        ) : veiculos.length === 0 ? (
          <EmptyState
            icon="car"
            title="Nenhum veículo encontrado"
            description="Cadastre um veículo ou altere os filtros."
            action={
              <button
                className="button button-primary"
                type="button"
                onClick={abrirNovo}
              >
                Cadastrar veículo
              </button>
            }
          />
        ) : (
          <div className="card-grid">
            {veiculos.map((item) => (
              <article className="entity-card" key={item.id}>
                <div className="entity-card-top">
                  <span className="entity-icon">
                    <Icon name="car" size={22} />
                  </span>
                  <div className="row-actions">
                    <button
                      className="icon-button"
                      type="button"
                      onClick={() => abrirEdicao(item)}
                      title="Editar veículo"
                    >
                      <Icon name="edit" size={17} />
                    </button>
                    <button
                      className="icon-button danger"
                      type="button"
                      onClick={() => solicitarExclusao(item)}
                      title="Excluir veículo"
                    >
                      <Icon name="trash" size={17} />
                    </button>
                  </div>
                </div>

                <h3>{item.apelido || item.modelo || "Veículo"}</h3>
                <p>{clienteNome(item.cliente_id)}</p>

                <dl className="entity-details">
                  <div>
                    <dt>Tipo</dt>
                    <dd>{tipoVeiculoLabel(item.tipo_veiculo)}</dd>
                  </div>
                  <div>
                    <dt>Modelo</dt>
                    <dd>{item.modelo ?? "—"}</dd>
                  </div>
                  <div>
                    <dt>Apelido</dt>
                    <dd>{item.apelido ?? "—"}</dd>
                  </div>
                  <div className="vehicle-observation">
                    <dt>Observações</dt>
                    <dd>{item.observacoes ?? "Nenhuma observação"}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        )}
      </section>

      <Modal
        open={modalAberto}
        title={editando ? "Editar veículo" : "Novo veículo"}
        subtitle="Vincule o veículo a um cliente e informe os dados essenciais."
        onClose={fecharModal}
        size="large"
      >
        <form onSubmit={salvar}>
          {erro && <Alert>{erro}</Alert>}

          <div className="form-grid form-grid-2">
            <label className="field field-span-2">
              Cliente
              <select
                value={form.cliente_id}
                onChange={(event) =>
                  setForm({ ...form, cliente_id: event.target.value })
                }
                required
                disabled={Boolean(editando)}
              >
                <option value="">Selecione o cliente</option>
                {clientes.map((cliente) => (
                  <option key={cliente.id} value={cliente.id}>
                    {cliente.nome}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              Tipo do veículo
              <select
                value={form.tipo_veiculo}
                onChange={(event) =>
                  setForm({
                    ...form,
                    tipo_veiculo: event.target.value as TipoVeiculo | "",
                  })
                }
                required
              >
                <option value="">Selecione o tipo</option>
                {tiposVeiculo.map((tipo) => (
                  <option key={tipo.value} value={tipo.value}>
                    {tipo.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              Modelo
              <input
                value={form.modelo}
                onChange={(event) =>
                  setForm({ ...form, modelo: event.target.value })
                }
                placeholder="Ex.: Gol, Onix, Corolla"
                required
              />
            </label>

            <label className="field field-span-2">
              Apelido
              <input
                value={form.apelido}
                onChange={(event) =>
                  setForm({ ...form, apelido: event.target.value })
                }
                placeholder="Ex.: Gol do João"
              />
            </label>

            <label className="field field-span-2">
              Observações
              <textarea
                rows={4}
                value={form.observacoes}
                onChange={(event) =>
                  setForm({ ...form, observacoes: event.target.value })
                }
                placeholder="Informações importantes sobre o veículo"
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
              {salvando ? "Salvando..." : "Salvar veículo"}
            </button>
          </div>
        </form>
      </Modal>

      <ConfirmationModal
        open={Boolean(veiculoExclusao)}
        title="Excluir veículo"
        heading={`Excluir ${
          veiculoExclusao ? displayVehicle(veiculoExclusao) : "este veículo"
        }?`}
        description="O veículo será removido do cadastro do cliente. Esta ação não pode ser desfeita."
        confirmLabel="Excluir veículo"
        onClose={fecharExclusao}
        onConfirm={() => void confirmarExclusao()}
        loading={excluindo}
        error={erro}
        tone="danger"
        icon="car"
      />
    </div>
  );
}
