import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";
import { Icon } from "../components/Icon";
import { Modal } from "../components/Modal";
import { Alert, EmptyState, LoadingState, PageHeader, StatusBadge } from "../components/UI";
import { apiRequest } from "../services/api";
import type { Servico, TipoVeiculo } from "../types";
import { formatCurrency, normalizeNullable } from "../utils/format";

interface ServicoForm {
  nome: string;
  descricao: string;
  duracao_minutos: string;
  preco: string;
  cor_agenda: string;
  ativo: boolean;
  adicional_por_tipo_ativo: boolean;
  adicionais: Record<TipoVeiculo, string>;
}

const tiposVeiculo: Array<{ value: TipoVeiculo; label: string }> = [
  { value: "HATCH", label: "Hatch" },
  { value: "SEDAN", label: "Sedã" },
  { value: "SUV", label: "SUV" },
  { value: "CAMINHONETE", label: "Caminhonete" },
  { value: "OUTRO", label: "Outro" },
];

const adicionaisVazios: Record<TipoVeiculo, string> = {
  HATCH: "0",
  SEDAN: "0",
  SUV: "0",
  CAMINHONETE: "0",
  OUTRO: "0",
};

function criarFormVazio(): ServicoForm {
  return {
    nome: "",
    descricao: "",
    duracao_minutos: "60",
    preco: "",
    cor_agenda: "#3157D5",
    ativo: true,
    adicional_por_tipo_ativo: false,
    adicionais: { ...adicionaisVazios },
  };
}

export function Servicos() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [servicos, setServicos] = useState<Servico[]>([]);
  const [busca, setBusca] = useState("");
  const [filtro, setFiltro] = useState("ativos");
  const [carregando, setCarregando] = useState(true);
  const [modalAberto, setModalAberto] = useState(searchParams.get("novo") === "1");
  const [editando, setEditando] = useState<Servico | null>(null);
  const [form, setForm] = useState<ServicoForm>(criarFormVazio());
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [servicoConfirmacao, setServicoConfirmacao] =
    useState<Servico | null>(null);
  const [alterandoSituacao, setAlterandoSituacao] = useState(false);
  const [erroConfirmacao, setErroConfirmacao] = useState("");
  const [limpezaAdicionaisAberta, setLimpezaAdicionaisAberta] =
    useState(false);

  async function carregar() {
    setCarregando(true);
    setErro("");
    try {
      const [ativos, inativos] = await Promise.all([
        apiRequest<Servico[]>("/servicos?ativo=true&limit=100"),
        apiRequest<Servico[]>("/servicos?ativo=false&limit=100"),
      ]);
      setServicos([...ativos, ...inativos].sort((a, b) => a.nome.localeCompare(b.nome)));
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível carregar os serviços.");
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    void carregar();
    if (searchParams.get("novo") === "1") {
      abrirNovo();
      setSearchParams({}, { replace: true });
    }
  }, []);

  useEffect(() => {
    if (!sucesso) return;

    const timer = window.setTimeout(() => {
      setSucesso("");
    }, 4000);

    return () => window.clearTimeout(timer);
  }, [sucesso]);

  const temAdicionaisConfigurados = useMemo(
    () =>
      tiposVeiculo.some(
        (tipo) =>
          Number(
            (form.adicionais[tipo.value] || "0").replace(",", "."),
          ) > 0,
      ),
    [form.adicionais],
  );

  const filtrados = useMemo(() => {
    const termo = busca.toLowerCase().trim();
    return servicos.filter((item) => {
      const statusOk =
        filtro === "todos" ||
        (filtro === "ativos" && item.ativo) ||
        (filtro === "inativos" && !item.ativo);
      const buscaOk =
        !termo ||
        item.nome.toLowerCase().includes(termo) ||
        item.descricao?.toLowerCase().includes(termo);
      return statusOk && buscaOk;
    });
  }, [busca, filtro, servicos]);

  function abrirNovo() {
    setEditando(null);
    setLimpezaAdicionaisAberta(false);
    setForm(criarFormVazio());
    setModalAberto(true);
    setErro("");
  }

  function abrirEdicao(item: Servico) {
    setEditando(item);
    setLimpezaAdicionaisAberta(false);
    const adicionais = { ...adicionaisVazios };
    item.adicionais.forEach((adicional) => {
      adicionais[adicional.tipo_veiculo] = String(adicional.valor_adicional);
    });

    setForm({
      nome: item.nome,
      descricao: item.descricao ?? "",
      duracao_minutos: item.duracao_minutos.toString(),
      preco: String(item.preco),
      cor_agenda: item.cor_agenda ?? "#3157D5",
      ativo: item.ativo,
      adicional_por_tipo_ativo: item.adicional_por_tipo_ativo,
      adicionais,
    });
    setModalAberto(true);
    setErro("");
  }

  function fecharModal() {
    setModalAberto(false);
    setEditando(null);
    setLimpezaAdicionaisAberta(false);
  }

  function abrirLimpezaAdicionais() {
    setLimpezaAdicionaisAberta(true);
  }

  function fecharLimpezaAdicionais() {
    setLimpezaAdicionaisAberta(false);
  }

  function confirmarLimpezaAdicionais() {
    setForm((atual) => ({
      ...atual,
      adicionais: { ...adicionaisVazios },
    }));
    setLimpezaAdicionaisAberta(false);
  }

  async function salvar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSalvando(true);
    setErro("");

    const payload = {
      nome: form.nome.trim(),
      descricao: normalizeNullable(form.descricao),
      duracao_minutos: Number(form.duracao_minutos),
      preco: Number(form.preco.replace(",", ".")),
      cor_agenda: form.cor_agenda || null,
      adicional_por_tipo_ativo: form.adicional_por_tipo_ativo,
      adicionais: tiposVeiculo.map((tipo) => ({
        tipo_veiculo: tipo.value,
        valor_adicional: Number(
          (form.adicionais[tipo.value] || "0").replace(",", "."),
        ),
      })),
      ...(editando ? { ativo: form.ativo } : {}),
    };

    try {
      if (editando) {
        await apiRequest<Servico>(`/servicos/${editando.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        setSucesso("Serviço atualizado com sucesso.");
      } else {
        await apiRequest<Servico>("/servicos", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setSucesso("Serviço cadastrado com sucesso.");
      }
      fecharModal();
      await carregar();
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível salvar o serviço.");
    } finally {
      setSalvando(false);
    }
  }

  function abrirConfirmacaoSituacao(item: Servico) {
    setServicoConfirmacao(item);
    setErroConfirmacao("");
  }

  function fecharConfirmacaoSituacao() {
    if (alterandoSituacao) return;

    setServicoConfirmacao(null);
    setErroConfirmacao("");
  }

  async function confirmarAlteracaoSituacao() {
    if (!servicoConfirmacao) return;

    setAlterandoSituacao(true);
    setErroConfirmacao("");

    try {
      if (servicoConfirmacao.ativo) {
        await apiRequest<void>(`/servicos/${servicoConfirmacao.id}`, {
          method: "DELETE",
        });
        setSucesso("Serviço desativado com sucesso.");
      } else {
        await apiRequest<Servico>(`/servicos/${servicoConfirmacao.id}`, {
          method: "PATCH",
          body: JSON.stringify({ ativo: true }),
        });
        setSucesso("Serviço reativado com sucesso.");
      }

      setServicoConfirmacao(null);
      await carregar();
    } catch (error) {
      setErroConfirmacao(
        error instanceof Error
          ? error.message
          : "Não foi possível alterar a situação do serviço.",
      );
    } finally {
      setAlterandoSituacao(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Catálogo"
        title="Serviços"
        description="Defina preços, duração e disponibilidade dos seus serviços."
        actions={
          <button className="button button-primary" type="button" onClick={abrirNovo}>
            <Icon name="plus" size={18} />
            Novo serviço
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

      {erro && !modalAberto && !servicoConfirmacao && <Alert>{erro}</Alert>}

      <section className="content-card">
        <div className="toolbar">
          <label className="search-field">
            <Icon name="search" size={18} />
            <input value={busca} onChange={(event) => setBusca(event.target.value)} placeholder="Buscar serviço" />
          </label>
          <select value={filtro} onChange={(event) => setFiltro(event.target.value)}>
            <option value="ativos">Ativos</option>
            <option value="inativos">Inativos</option>
            <option value="todos">Todos</option>
          </select>
        </div>

        {carregando ? (
          <LoadingState label="Carregando serviços..." />
        ) : filtrados.length === 0 ? (
          <EmptyState
            icon="services"
            title="Nenhum serviço encontrado"
            description="Cadastre um serviço para começar a montar sua agenda."
            action={<button className="button button-primary" onClick={abrirNovo}>Cadastrar serviço</button>}
          />
        ) : (
          <div className="service-grid">
            {filtrados.map((item) => (
              <article className={`service-card ${!item.ativo ? "service-card-inactive" : ""}`} key={item.id}>
                <div className="service-color" style={{ background: item.cor_agenda ?? "#3157D5" }} />
                <div className="service-card-header">
                  <div>
                    <StatusBadge value={item.ativo ? "ATIVO" : "INATIVO"} />
                    <h3>{item.nome}</h3>
                  </div>
                  <div className="row-actions">
                    <button className="icon-button" type="button" onClick={() => abrirEdicao(item)}><Icon name="edit" size={17} /></button>
                    <button
                      className={`icon-button ${
                        item.ativo ? "danger" : "success"
                      }`}
                      type="button"
                      onClick={() => abrirConfirmacaoSituacao(item)}
                      title={item.ativo ? "Desativar serviço" : "Reativar serviço"}
                    >
                      <Icon
                        name={item.ativo ? "pause" : "refresh"}
                        size={17}
                      />
                    </button>
                  </div>
                </div>
                <p>{item.descricao || "Sem descrição cadastrada."}</p>
                {item.adicional_por_tipo_ativo && (
                  <span className="service-addon-badge">
                    <Icon name="car" size={14} />
                    Adicional por tipo de veículo
                  </span>
                )}
                <div className="service-meta">
                  <span><Icon name="clock" size={16} /> {item.duracao_minutos} min</span>
                  <strong>{formatCurrency(item.preco)}</strong>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <Modal open={modalAberto} title={editando ? "Editar serviço" : "Novo serviço"} subtitle="Configure os dados comerciais e o tempo de atendimento." onClose={fecharModal}>
        <form onSubmit={salvar}>
          {erro && <Alert>{erro}</Alert>}
          <div className="form-grid form-grid-2">
            <label className="field field-span-2">
              Nome
              <input value={form.nome} onChange={(event) => setForm({ ...form, nome: event.target.value })} required minLength={2} />
            </label>
            <label className="field">
              Duração em minutos
              <input type="number" min="1" max="1440" value={form.duracao_minutos} onChange={(event) => setForm({ ...form, duracao_minutos: event.target.value })} required />
            </label>
            <label className="field">
              Preço
              <input type="number" min="0" step="0.01" value={form.preco} onChange={(event) => setForm({ ...form, preco: event.target.value })} required />
            </label>
            <label className="field">
              Cor na agenda
              <div className="color-field">
                <input type="color" value={form.cor_agenda} onChange={(event) => setForm({ ...form, cor_agenda: event.target.value })} />
                <input value={form.cor_agenda} onChange={(event) => setForm({ ...form, cor_agenda: event.target.value })} maxLength={7} />
              </div>
            </label>
            {editando && (
              <label className="field checkbox-field">
                <input type="checkbox" checked={form.ativo} onChange={(event) => setForm({ ...form, ativo: event.target.checked })} />
                Serviço ativo
              </label>
            )}
            <label className="field field-span-2">
              Descrição
              <textarea rows={4} value={form.descricao} onChange={(event) => setForm({ ...form, descricao: event.target.value })} />
            </label>

            <div className="vehicle-addon-settings field-span-2">
              <div className="vehicle-addon-header">
                <label className="vehicle-addon-toggle">
                  <span className="switch-control">
                    <input
                      type="checkbox"
                      checked={form.adicional_por_tipo_ativo}
                      onChange={(event) =>
                        setForm({
                          ...form,
                          adicional_por_tipo_ativo: event.target.checked,
                        })
                      }
                    />
                    <span className="switch-slider" />
                  </span>
                  <span className="vehicle-addon-toggle-copy">
                    <strong>Adicional por tipo de veículo</strong>
                    <small>
                      Some um valor ao preço base conforme o porte do veículo.
                    </small>
                  </span>
                </label>

                {form.adicional_por_tipo_ativo && (
                  <button
                    className="vehicle-addon-clear"
                    type="button"
                    onClick={abrirLimpezaAdicionais}
                    disabled={!temAdicionaisConfigurados}
                  >
                    <Icon name="trash" size={15} />
                    Limpar adicionais
                  </button>
                )}
              </div>

              {form.adicional_por_tipo_ativo && (
                <div className="vehicle-addon-grid">
                  {tiposVeiculo.map((tipo) => (
                    <label className="field" key={tipo.value}>
                      {tipo.label}
                      <div className="money-field">
                        <span>R$</span>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={form.adicionais[tipo.value]}
                          onChange={(event) =>
                            setForm({
                              ...form,
                              adicionais: {
                                ...form.adicionais,
                                [tipo.value]: event.target.value,
                              },
                            })
                          }
                        />
                      </div>
                    </label>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div className="modal-actions">
            <button className="button button-secondary" type="button" onClick={fecharModal}>Cancelar</button>
            <button className="button button-primary" type="submit" disabled={salvando}>{salvando ? "Salvando..." : "Salvar serviço"}</button>
          </div>
        </form>
      </Modal>

      <Modal
        open={limpezaAdicionaisAberta}
        title="Limpar adicionais"
        subtitle="Confirme antes de zerar a configuração."
        onClose={fecharLimpezaAdicionais}
        size="small"
      >
        <div className="confirmation-dialog">
          <span className="confirmation-icon confirmation-icon-danger">
            <Icon name="trash" size={24} />
          </span>

          <div className="confirmation-copy">
            <strong>Zerar todos os adicionais deste serviço?</strong>
            <p>
              Hatch, Sedã, SUV, Caminhonete e Outro serão definidos como
              R$ 0,00. A mudança só será aplicada depois de clicar em
              Salvar serviço.
            </p>
          </div>

          <div className="modal-actions confirmation-actions">
            <button
              className="button button-secondary"
              type="button"
              onClick={fecharLimpezaAdicionais}
            >
              Cancelar
            </button>
            <button
              className="button button-danger"
              type="button"
              onClick={confirmarLimpezaAdicionais}
            >
              Limpar adicionais
            </button>
          </div>
        </div>
      </Modal>

      <Modal
        open={Boolean(servicoConfirmacao)}
        title={
          servicoConfirmacao?.ativo
            ? "Desativar serviço"
            : "Reativar serviço"
        }
        subtitle="Confirme a alteração antes de continuar."
        onClose={fecharConfirmacaoSituacao}
        size="small"
      >
        {servicoConfirmacao && (
          <div className="confirmation-dialog">
            <span
              className={`confirmation-icon ${
                servicoConfirmacao.ativo
                  ? "confirmation-icon-danger"
                  : "confirmation-icon-success"
              }`}
            >
              <Icon
                name={servicoConfirmacao.ativo ? "pause" : "refresh"}
                size={24}
              />
            </span>

            <div className="confirmation-copy">
              <strong>
                {servicoConfirmacao.ativo
                  ? `Desativar ${servicoConfirmacao.nome}?`
                  : `Reativar ${servicoConfirmacao.nome}?`}
              </strong>
              <p>
                {servicoConfirmacao.ativo
                  ? "O serviço ficará indisponível para novos agendamentos e poderá ser reativado posteriormente."
                  : "O serviço voltará a ficar disponível para novos agendamentos."}
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
                  servicoConfirmacao.ativo
                    ? "button button-danger"
                    : "button button-primary"
                }
                type="button"
                onClick={() => void confirmarAlteracaoSituacao()}
                disabled={alterandoSituacao}
              >
                {alterandoSituacao
                  ? "Processando..."
                  : servicoConfirmacao.ativo
                    ? "Desativar serviço"
                    : "Reativar serviço"}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
