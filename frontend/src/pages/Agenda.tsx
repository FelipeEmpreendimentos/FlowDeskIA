import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";
import { Icon } from "../components/Icon";
import { Modal } from "../components/Modal";
import { Alert, EmptyState, LoadingState, PageHeader, StatusBadge } from "../components/UI";
import { apiRequest, buildQuery } from "../services/api";
import type {
  Agendamento,
  Cliente,
  FormaPagamento,
  Servico,
  SlotDisponivel,
  StatusAgendamento,
  TipoVeiculo,
  Usuario,
  Veiculo,
} from "../types";
import {
  displayVehicle,
  formatCurrency,
  formatDate,
  formatTime,
  normalizeNullable,
  todayISO,
} from "../utils/format";

interface AgendaForm {
  cliente_id: string;
  veiculo_id: string;
  tipo_veiculo: TipoVeiculo | "";
  servico_id: string;
  funcionario_id: string;
  data: string;
  hora_inicio: string;
  status: StatusAgendamento;
  valor_base: string;
  valor_adicional: string;
  valor_final: string;
  forma_pagamento: FormaPagamento | "";
  observacoes: string;
}

const formVazio: AgendaForm = {
  cliente_id: "",
  veiculo_id: "",
  tipo_veiculo: "",
  servico_id: "",
  funcionario_id: "",
  data: todayISO(),
  hora_inicio: "",
  status: "PENDENTE",
  valor_base: "",
  valor_adicional: "",
  valor_final: "",
  forma_pagamento: "",
  observacoes: "",
};

type AgendaModo = "agenda" | "historico";

const statusOptions: StatusAgendamento[] = [
  "PENDENTE",
  "CONFIRMADO",
  "EM_ANDAMENTO",
  "FINALIZADO",
  "CANCELADO",
];

const statusAgenda: StatusAgendamento[] = [
  "PENDENTE",
  "CONFIRMADO",
  "EM_ANDAMENTO",
];

const statusHistorico: StatusAgendamento[] = [
  "FINALIZADO",
  "CANCELADO",
];

const tiposVeiculo: Array<{ value: TipoVeiculo; label: string }> = [
  { value: "HATCH", label: "Hatch" },
  { value: "SEDAN", label: "Sedã" },
  { value: "SUV", label: "SUV" },
  { value: "CAMINHONETE", label: "Caminhonete" },
  { value: "OUTRO", label: "Outro" },
];

const tipoVeiculoLabel = (tipo: TipoVeiculo | null | undefined) =>
  tiposVeiculo.find((item) => item.value === tipo)?.label ?? "Não informado";

function deslocarData(dataIso: string, dias: number): string {
  const [ano, mes, dia] = dataIso.split("-").map(Number);
  const data = new Date(ano, mes - 1, dia);
  data.setDate(data.getDate() + dias);
  const local = new Date(data.getTime() - data.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

function ontemISO(): string {
  return deslocarData(todayISO(), -1);
}

function primeiroDiaDaSemana(): string {
  const hoje = todayISO();
  const [ano, mes, dia] = hoje.split("-").map(Number);
  const data = new Date(ano, mes - 1, dia);
  const diaSemana = data.getDay();
  const distanciaAteSegunda = diaSemana === 0 ? -6 : 1 - diaSemana;
  return deslocarData(hoje, distanciaAteSegunda);
}

function primeiroDiaDoMes(): string {
  const hoje = todayISO();
  return `${hoje.slice(0, 7)}-01`;
}

export function Agenda() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [modo, setModo] = useState<AgendaModo>("agenda");
  const [dataFiltro, setDataFiltro] = useState(todayISO());
  const [dataInicioHistorico, setDataInicioHistorico] = useState(ontemISO());
  const [dataFimHistorico, setDataFimHistorico] = useState(todayISO());
  const [statusFiltro, setStatusFiltro] = useState("");
  const [funcionarioFiltro, setFuncionarioFiltro] = useState("");
  const [agendamentos, setAgendamentos] = useState<Agendamento[]>([]);
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [servicos, setServicos] = useState<Servico[]>([]);
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [veiculos, setVeiculos] = useState<Veiculo[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [modalAberto, setModalAberto] = useState(searchParams.get("novo") === "1");
  const [editando, setEditando] = useState<Agendamento | null>(null);
  const [form, setForm] = useState<AgendaForm>(formVazio);
  const [slots, setSlots] = useState<SlotDisponivel[]>([]);
  const [buscandoSlots, setBuscandoSlots] = useState(false);
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");
  const [avisoDisponibilidade, setAvisoDisponibilidade] = useState("");
  const [salvando, setSalvando] = useState(false);

  async function carregarApoio() {
    const [dadosClientes, dadosServicos, dadosUsuarios, dadosVeiculos] = await Promise.all([
      apiRequest<Cliente[]>("/clientes?status_cliente=ATIVO&limit=100"),
      apiRequest<Servico[]>("/servicos?ativo=true&limit=100"),
      apiRequest<Usuario[]>("/usuarios?ativo=true&limit=100"),
      apiRequest<Veiculo[]>("/veiculos?limit=100"),
    ]);
    setClientes(dadosClientes);
    setServicos(dadosServicos);
    setUsuarios(dadosUsuarios);
    setVeiculos(dadosVeiculos);
  }

  async function carregarAgenda() {
    setCarregando(true);
    setErro("");

    const dataInicio = modo === "agenda" ? dataFiltro : dataInicioHistorico;
    const dataFim = modo === "agenda" ? dataFiltro : dataFimHistorico;
    const statusPermitidos = modo === "agenda" ? statusAgenda : statusHistorico;

    try {
      const data = await apiRequest<Agendamento[]>(
        `/agendamentos${buildQuery({
          data_inicio: dataInicio,
          data_fim: dataFim,
          status_agendamento: statusFiltro,
          funcionario_id: funcionarioFiltro,
          limit: 200,
        })}`,
      );

      const unicos = Array.from(
        new Map(data.map((item) => [item.id, item])).values(),
      );

      setAgendamentos(
        unicos.filter((item) => statusPermitidos.includes(item.status)),
      );
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível carregar os agendamentos.",
      );
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    async function iniciar() {
      try {
        await carregarApoio();
      } catch (error) {
        setErro(error instanceof Error ? error.message : "Não foi possível carregar os dados da agenda.");
      }
    }
    void iniciar();

    if (searchParams.get("novo") === "1") {
      setModalAberto(true);
      setSearchParams({}, { replace: true });
    }
  }, []);

  useEffect(() => {
    void carregarAgenda();
  }, [
    modo,
    dataFiltro,
    dataInicioHistorico,
    dataFimHistorico,
    statusFiltro,
    funcionarioFiltro,
  ]);


  useEffect(() => {
    if (!avisoDisponibilidade) return;

    const timer = window.setTimeout(() => {
      setAvisoDisponibilidade("");
    }, 4000);

    return () => window.clearTimeout(timer);
  }, [avisoDisponibilidade]);

  const ordenados = useMemo(() => {
    const itens = [...agendamentos];

    if (modo === "historico") {
      return itens.sort((a, b) => {
        const porData = b.data.localeCompare(a.data);
        return porData !== 0
          ? porData
          : b.hora_inicio.localeCompare(a.hora_inicio);
      });
    }

    return itens.sort((a, b) => a.hora_inicio.localeCompare(b.hora_inicio));
  }, [agendamentos, modo]);

  const opcoesStatus =
    modo === "agenda" ? statusAgenda : statusHistorico;

  function trocarModo(novoModo: AgendaModo) {
    setModo(novoModo);
    setStatusFiltro("");
    setErro("");
    setSucesso("");
  }

  const veiculosCliente = useMemo(
    () => veiculos.filter((item) => item.cliente_id === Number(form.cliente_id)),
    [form.cliente_id, veiculos],
  );

  const servicoSelecionado = useMemo(
    () => servicos.find((item) => item.id === Number(form.servico_id)) ?? null,
    [form.servico_id, servicos],
  );

  const veiculoSelecionado = useMemo(
    () => veiculos.find((item) => item.id === Number(form.veiculo_id)) ?? null,
    [form.veiculo_id, veiculos],
  );

  const tipoVeiculoEfetivo =
    veiculoSelecionado?.tipo_veiculo ?? (form.tipo_veiculo || null);

  function calcularPreco(
    servicoId: string,
    veiculoId: string,
    tipoManual: TipoVeiculo | "",
  ) {
    const servico = servicos.find((item) => item.id === Number(servicoId));
    if (!servico) {
      return { valor_base: "", valor_adicional: "", valor_final: "" };
    }

    const veiculo = veiculos.find((item) => item.id === Number(veiculoId));
    const tipo = veiculo?.tipo_veiculo ?? (tipoManual || null);
    const valorBase = Number(servico.preco);
    const adicional =
      servico.adicional_por_tipo_ativo && tipo
        ? Number(
            servico.adicionais.find(
              (item) => item.tipo_veiculo === tipo,
            )?.valor_adicional ?? 0,
          )
        : 0;

    return {
      valor_base: valorBase.toFixed(2),
      valor_adicional: adicional.toFixed(2),
      valor_final: (valorBase + adicional).toFixed(2),
    };
  }

  const slotSelecionado = useMemo(() => {
    const encontrado = slots.find(
      (slot) => formatTime(slot.hora_inicio) === form.hora_inicio,
    );

    if (encontrado) {
      return encontrado;
    }

    if (
      editando &&
      form.hora_inicio === formatTime(editando.hora_inicio)
    ) {
      return {
        hora_inicio: editando.hora_inicio,
        hora_fim: editando.hora_fim,
      };
    }

    return null;
  }, [editando, form.hora_inicio, slots]);

  const clienteNome = (id: number) =>
    clientes.find((item) => item.id === id)?.nome ?? `Cliente #${id}`;
  const servicoNome = (id: number) =>
    servicos.find((item) => item.id === id)?.nome ?? `Serviço #${id}`;
  const usuarioNome = (id: number | null) =>
    id ? usuarios.find((item) => item.id === id)?.nome ?? `Usuário #${id}` : "Sem responsável";
  const veiculoNome = (id: number | null) =>
    id ? displayVehicle(veiculos.find((item) => item.id === id) ?? {
      marca: null,
      modelo: null,
      placa: null,
      apelido: `Veículo #${id}`,
    }) : "Sem veículo";

  function abrirNovo() {
    setEditando(null);
    setForm({
      ...formVazio,
      data: dataFiltro,
    });
    setSlots([]);
    setErro("");
    setAvisoDisponibilidade("");
    setModalAberto(true);
  }

  function abrirEdicao(item: Agendamento) {
    setEditando(item);
    setForm({
      cliente_id: item.cliente_id.toString(),
      veiculo_id: item.veiculo_id?.toString() ?? "",
      tipo_veiculo: item.tipo_veiculo_cobrado ?? "",
      servico_id: item.servico_id.toString(),
      funcionario_id: item.funcionario_id?.toString() ?? "",
      data: item.data,
      hora_inicio: formatTime(item.hora_inicio),
      status: item.status,
      valor_base: String(item.valor_base),
      valor_adicional: String(item.valor_adicional),
      valor_final: item.valor_final != null ? String(item.valor_final) : "",
      forma_pagamento: item.forma_pagamento ?? "",
      observacoes: item.observacoes ?? "",
    });
    setAvisoDisponibilidade("");
    setSlots([
      {
        hora_inicio: item.hora_inicio,
        hora_fim: item.hora_fim,
      },
    ]);
    setErro("");
    setModalAberto(true);
  }

  function fecharModal() {
    setModalAberto(false);
    setEditando(null);
    setSlots([]);
    setErro("");
  }

  function selecionarServico(id: string) {
    const calculo = calcularPreco(id, form.veiculo_id, form.tipo_veiculo);
    setForm({
      ...form,
      servico_id: id,
      hora_inicio: "",
      ...calculo,
    });
    setSlots([]);
  }

  function selecionarVeiculo(id: string) {
    const veiculo = veiculos.find((item) => item.id === Number(id));
    const tipo = veiculo?.tipo_veiculo ?? "";
    const calculo = calcularPreco(form.servico_id, id, tipo);
    setForm({
      ...form,
      veiculo_id: id,
      tipo_veiculo: tipo,
      ...calculo,
    });
  }

  function selecionarTipoVeiculo(tipo: TipoVeiculo | "") {
    const calculo = calcularPreco(form.servico_id, form.veiculo_id, tipo);
    setForm({
      ...form,
      tipo_veiculo: tipo,
      ...calculo,
    });
  }

  async function consultarDisponibilidade() {
    if (!form.data || !form.servico_id || !form.funcionario_id) {
      setErro("Selecione data, serviço e funcionário para consultar horários.");
      return;
    }

    setBuscandoSlots(true);
    setErro("");
    setAvisoDisponibilidade("");
    try {
      const data = await apiRequest<SlotDisponivel[]>(
        `/agendamentos/disponibilidade${buildQuery({
          data: form.data,
          servico_id: form.servico_id,
          funcionario_id: form.funcionario_id,
          intervalo_minutos: 30,
        })}`,
      );
      const horarioAtualPodeContinuar =
        editando &&
        form.data === editando.data &&
        Number(form.servico_id) === editando.servico_id &&
        Number(form.funcionario_id) === editando.funcionario_id;

      const opcoes = horarioAtualPodeContinuar
        ? [
            {
              hora_inicio: editando.hora_inicio,
              hora_fim: editando.hora_fim,
            },
            ...data,
          ]
        : data;

      const slotsUnicos = Array.from(
        new Map(
          opcoes.map((slot) => [
            `${slot.hora_inicio}-${slot.hora_fim}`,
            slot,
          ]),
        ).values(),
      ).sort((a, b) => a.hora_inicio.localeCompare(b.hora_inicio));

      setSlots(slotsUnicos);

      if (slotsUnicos.length === 0) {
        setAvisoDisponibilidade(
          "Não há horários disponíveis para atendimento.",
        );
      }
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível consultar a disponibilidade.");
    } finally {
      setBuscandoSlots(false);
    }
  }

  async function salvar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro("");

    if (!form.funcionario_id) {
      setErro("Selecione um funcionário para consultar a disponibilidade.");
      return;
    }

    if (servicoSelecionado?.adicional_por_tipo_ativo && !tipoVeiculoEfetivo) {
      setErro("Selecione o tipo do veículo para calcular o valor do serviço.");
      return;
    }

    if (!form.hora_inicio || !slotSelecionado) {
      setErro(
        "Clique em “Buscar horários disponíveis” e selecione um horário antes de salvar.",
      );
      return;
    }

    setSalvando(true);

    const common = {
      veiculo_id: form.veiculo_id ? Number(form.veiculo_id) : null,
      tipo_veiculo: tipoVeiculoEfetivo,
      servico_id: Number(form.servico_id),
      funcionario_id: form.funcionario_id ? Number(form.funcionario_id) : null,
      data: form.data,
      hora_inicio: `${form.hora_inicio}:00`,
      status: form.status,
      forma_pagamento: form.forma_pagamento || null,
      observacoes: normalizeNullable(form.observacoes),
    };

    try {
      if (editando) {
        await apiRequest<Agendamento>(`/agendamentos/${editando.id}`, {
          method: "PATCH",
          body: JSON.stringify(common),
        });
        setSucesso("Agendamento atualizado.");
      } else {
        await apiRequest<Agendamento>("/agendamentos", {
          method: "POST",
          body: JSON.stringify({
            cliente_id: Number(form.cliente_id),
            origem: "FUNCIONARIO",
            ...common,
          }),
        });
        setSucesso("Agendamento criado.");
      }

      fecharModal();
      setDataFiltro(form.data);
      await carregarAgenda();
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível salvar o agendamento.");
    } finally {
      setSalvando(false);
    }
  }

  async function mudarStatus(item: Agendamento, status: StatusAgendamento) {
    try {
      await apiRequest<Agendamento>(`/agendamentos/${item.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      setSucesso(`Agendamento alterado para ${status.toLowerCase().replaceAll("_", " ")}.`);
      await carregarAgenda();
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível alterar o agendamento.");
    }
  }

  async function cancelar(item: Agendamento) {
    const confirmado = window.confirm(
      `Cancelar o agendamento de ${clienteNome(item.cliente_id)}?\n\n` +
        "O horário será liberado e o registro continuará salvo no Histórico.",
    );

    if (!confirmado) return;
    try {
      await apiRequest<void>(`/agendamentos/${item.id}`, { method: "DELETE" });
      setSucesso("Agendamento cancelado.");
      await carregarAgenda();
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível cancelar o agendamento.");
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Operação"
        title="Agenda"
        description="Visualize horários, crie atendimentos e acompanhe cada etapa."
        actions={
          <button className="button button-primary" type="button" onClick={abrirNovo}>
            <Icon name="plus" size={18} />
            Novo agendamento
          </button>
        }
      />

      {avisoDisponibilidade && (
        <div className="app-toast-region" aria-live="polite" aria-atomic="true">
          <div className="app-toast app-toast-warning" role="status">
            <span className="app-toast-icon app-toast-icon-warning">
              <Icon name="clock" size={18} />
            </span>
            <div className="app-toast-copy">
              <strong>Sem horários disponíveis</strong>
              <span>{avisoDisponibilidade}</span>
            </div>
            <button
              className="app-toast-close"
              type="button"
              onClick={() => setAvisoDisponibilidade("")}
              aria-label="Fechar notificação"
            >
              <Icon name="close" size={17} />
            </button>
          </div>
        </div>
      )}

      {sucesso && <Alert type="success">{sucesso}</Alert>}
      {erro && !modalAberto && <Alert>{erro}</Alert>}

      <section className="content-card">
        <div className="agenda-tabs" role="tablist" aria-label="Visualização dos agendamentos">
          <button
            className={`agenda-tab ${modo === "agenda" ? "agenda-tab-active" : ""}`}
            type="button"
            role="tab"
            aria-selected={modo === "agenda"}
            onClick={() => trocarModo("agenda")}
          >
            <Icon name="calendar" size={17} />
            Agenda
          </button>

          <button
            className={`agenda-tab ${modo === "historico" ? "agenda-tab-active" : ""}`}
            type="button"
            role="tab"
            aria-selected={modo === "historico"}
            onClick={() => trocarModo("historico")}
          >
            <Icon name="clock" size={17} />
            Histórico
          </button>
        </div>

        <div className="agenda-toolbar">
          {modo === "agenda" ? (
            <label className="field compact-field">
              Data
              <input
                type="date"
                value={dataFiltro}
                onChange={(event) => setDataFiltro(event.target.value)}
              />
            </label>
          ) : (
            <>
              <label className="field compact-field">
                Data inicial
                <input
                  type="date"
                  value={dataInicioHistorico}
                  max={dataFimHistorico}
                  onChange={(event) => setDataInicioHistorico(event.target.value)}
                />
              </label>

              <label className="field compact-field">
                Data final
                <input
                  type="date"
                  value={dataFimHistorico}
                  min={dataInicioHistorico}
                  onChange={(event) => setDataFimHistorico(event.target.value)}
                />
              </label>
            </>
          )}

          <label className="field compact-field">
            Status
            <select
              value={statusFiltro}
              onChange={(event) => setStatusFiltro(event.target.value)}
            >
              <option value="">
                {modo === "agenda" ? "Todos os ativos" : "Todo o histórico"}
              </option>
              {opcoesStatus.map((item) => (
                <option key={item} value={item}>
                  {item.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>

          <label className="field compact-field">
            Funcionário
            <select
              value={funcionarioFiltro}
              onChange={(event) => setFuncionarioFiltro(event.target.value)}
            >
              <option value="">Todos</option>
              {usuarios.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.nome}
                </option>
              ))}
            </select>
          </label>

          {modo === "agenda" ? (
            <button
              className="button button-ghost"
              type="button"
              onClick={() => {
                setDataFiltro(todayISO());
                setStatusFiltro("");
                setFuncionarioFiltro("");
              }}
            >
              Hoje
            </button>
          ) : (
            <div className="history-shortcuts" aria-label="Atalhos de período">
              <button
                className="button button-ghost"
                type="button"
                onClick={() => {
                  setDataInicioHistorico(todayISO());
                  setDataFimHistorico(todayISO());
                }}
              >
                Hoje
              </button>
              <button
                className="button button-ghost"
                type="button"
                onClick={() => {
                  setDataInicioHistorico(primeiroDiaDaSemana());
                  setDataFimHistorico(todayISO());
                }}
              >
                Esta semana
              </button>
              <button
                className="button button-ghost"
                type="button"
                onClick={() => {
                  setDataInicioHistorico(primeiroDiaDoMes());
                  setDataFimHistorico(todayISO());
                }}
              >
                Este mês
              </button>
            </div>
          )}
        </div>

        <div className="agenda-date-heading">
          <div>
            <span>{modo === "agenda" ? "Agenda do dia" : "Histórico de agendamentos"}</span>
            <h2>
              {modo === "agenda"
                ? formatDate(dataFiltro)
                : `${formatDate(dataInicioHistorico)} até ${formatDate(dataFimHistorico)}`}
            </h2>
          </div>

          <strong>
            {agendamentos.length} registro{agendamentos.length === 1 ? "" : "s"}
          </strong>
        </div>

        {modo === "agenda" && (
          <div className="agenda-info">
            Cancelados e finalizados ficam organizados na aba Histórico.
          </div>
        )}

        {carregando ? (
          <LoadingState
            label={
              modo === "agenda"
                ? "Carregando agenda..."
                : "Carregando histórico..."
            }
          />
        ) : ordenados.length === 0 ? (
          <EmptyState
            icon={modo === "agenda" ? "calendar" : "clock"}
            title={modo === "agenda" ? "Agenda livre" : "Histórico vazio"}
            description={
              modo === "agenda"
                ? "Não há agendamentos ativos com os filtros selecionados."
                : "Não há agendamentos finalizados ou cancelados nesse período."
            }
            action={
              modo === "agenda" ? (
                <button className="button button-primary" onClick={abrirNovo}>
                  Criar agendamento
                </button>
              ) : undefined
            }
          />
        ) : (
          <div className="timeline">
            {ordenados.map((item) => (
              <article
                className={`timeline-item timeline-${item.status
                  .toLowerCase()
                  .replaceAll("_", "-")}`}
                key={item.id}
              >
                <div className="timeline-time">
                  <strong>{formatTime(item.hora_inicio)}</strong>
                  <span>{formatTime(item.hora_fim)}</span>
                  {modo === "historico" && <small>{formatDate(item.data)}</small>}
                </div>

                <span
                  className="timeline-marker"
                  style={{
                    background:
                      servicos.find(
                        (servico) => servico.id === item.servico_id,
                      )?.cor_agenda ?? "#3157D5",
                  }}
                />

                <div className="timeline-content">
                  <div className="timeline-main">
                    <div>
                      <h3>{clienteNome(item.cliente_id)}</h3>
                      <p>
                        {servicoNome(item.servico_id)} ·{" "}
                        {veiculoNome(item.veiculo_id)}
                      </p>
                    </div>
                    <StatusBadge value={item.status} />
                  </div>

                  <div className="timeline-footer">
                    <span>
                      <Icon name="team" size={15} />{" "}
                      {usuarioNome(item.funcionario_id)}
                    </span>
                    <div className="timeline-price">
                      <strong>{formatCurrency(item.valor_final)}</strong>
                      {Number(item.valor_adicional) > 0 && (
                        <small>
                          {formatCurrency(item.valor_base)} + {formatCurrency(item.valor_adicional)}
                        </small>
                      )}
                    </div>

                    <div className="row-actions">
                      {modo === "agenda" && item.status === "PENDENTE" && (
                        <button
                          className="small-action success"
                          onClick={() =>
                            void mudarStatus(item, "CONFIRMADO")
                          }
                        >
                          Confirmar
                        </button>
                      )}

                      {modo === "agenda" && item.status === "CONFIRMADO" && (
                        <button
                          className="small-action"
                          onClick={() =>
                            void mudarStatus(item, "EM_ANDAMENTO")
                          }
                        >
                          Iniciar
                        </button>
                      )}

                      {modo === "agenda" && item.status === "EM_ANDAMENTO" && (
                        <button
                          className="small-action success"
                          onClick={() =>
                            void mudarStatus(item, "FINALIZADO")
                          }
                        >
                          Finalizar
                        </button>
                      )}

                      <button
                        className="icon-button"
                        type="button"
                        onClick={() => abrirEdicao(item)}
                        title="Editar"
                      >
                        <Icon name="edit" size={17} />
                      </button>

                      {modo === "agenda" &&
                        !["FINALIZADO", "CANCELADO"].includes(item.status) && (
                          <button
                            className="icon-button danger"
                            type="button"
                            onClick={() => void cancelar(item)}
                            title="Cancelar agendamento"
                          >
                            <Icon name="close" size={17} />
                          </button>
                        )}
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <Modal
        open={modalAberto}
        title={editando ? "Editar agendamento" : "Novo agendamento"}
        subtitle="Selecione cliente, serviço, profissional e horário."
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
                  setForm({
                    ...form,
                    cliente_id: event.target.value,
                    veiculo_id: "",
                    tipo_veiculo: "",
                    ...calcularPreco(form.servico_id, "", ""),
                  })
                }
                required
                disabled={Boolean(editando)}
              >
                <option value="">Selecione</option>
                {clientes.map((item) => <option key={item.id} value={item.id}>{item.nome}</option>)}
              </select>
            </label>
            <label className="field">
              Veículo
              <select
                value={form.veiculo_id}
                onChange={(event) => selecionarVeiculo(event.target.value)}
                disabled={!form.cliente_id || veiculosCliente.length === 0}
              >
                {!form.cliente_id ? (
                  <option value="">Selecione primeiro o cliente</option>
                ) : veiculosCliente.length === 0 ? (
                  <option value="">Sem veículo</option>
                ) : (
                  <>
                    <option value="">Selecione</option>
                    {veiculosCliente.map((item) => (
                      <option key={item.id} value={item.id}>
                        {displayVehicle(item)}
                      </option>
                    ))}
                  </>
                )}
              </select>
            </label>
            <label className="field">
              Serviço
              <select value={form.servico_id} onChange={(event) => selecionarServico(event.target.value)} required>
                <option value="">Selecione</option>
                {servicos.map((item) => <option key={item.id} value={item.id}>{item.nome} — {formatCurrency(item.preco)}</option>)}
              </select>
            </label>
            {servicoSelecionado?.adicional_por_tipo_ativo && (
              <label className="field field-span-2">
                Tipo do veículo para este atendimento
                <select
                  value={tipoVeiculoEfetivo ?? ""}
                  onChange={(event) =>
                    selecionarTipoVeiculo(
                      event.target.value as TipoVeiculo | "",
                    )
                  }
                  disabled={Boolean(veiculoSelecionado?.tipo_veiculo)}
                  required
                >
                  <option value="">Selecione</option>
                  {tiposVeiculo.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
                <small>
                  {veiculoSelecionado?.tipo_veiculo
                    ? `Tipo identificado no cadastro: ${tipoVeiculoLabel(
                        veiculoSelecionado.tipo_veiculo,
                      )}.`
                    : "Obrigatório para calcular o adicional deste serviço."}
                </small>
              </label>
            )}
            <label className="field">
              Funcionário
              <select
                value={form.funcionario_id}
                onChange={(event) => {
                  setForm({
                    ...form,
                    funcionario_id: event.target.value,
                    hora_inicio: "",
                  });
                  setSlots([]);
                }}
                required
              >
                <option value="">Selecione</option>
                {usuarios.map((item) => <option key={item.id} value={item.id}>{item.nome}</option>)}
              </select>
            </label>
            <label className="field">
              Data
              <input
                type="date"
                value={form.data}
                onChange={(event) => {
                  setForm({
                    ...form,
                    data: event.target.value,
                    hora_inicio: "",
                  });
                  setSlots([]);
                }}
                required
              />
            </label>
            <div className="field field-span-2 schedule-picker">
              <span>Horário do agendamento</span>

              <button
                className="button button-secondary schedule-search-button"
                type="button"
                onClick={() => void consultarDisponibilidade()}
                disabled={
                  buscandoSlots ||
                  !form.data ||
                  !form.servico_id ||
                  !form.funcionario_id
                }
              >
                <Icon name="clock" size={17} />
                {buscandoSlots
                  ? "Buscando horários..."
                  : "Buscar horários disponíveis"}
              </button>

              <small>
                Escolha primeiro o serviço, o funcionário e a data.
              </small>
            </div>

            {slots.length > 0 && (
              <div className="slots field-span-2" aria-label="Horários disponíveis">
                {slots.map((slot) => (
                  <button
                    key={`${slot.hora_inicio}-${slot.hora_fim}`}
                    type="button"
                    className={
                      formatTime(slot.hora_inicio) === form.hora_inicio
                        ? "slot-active"
                        : ""
                    }
                    onClick={() =>
                      setForm({
                        ...form,
                        hora_inicio: formatTime(slot.hora_inicio),
                      })
                    }
                  >
                    {formatTime(slot.hora_inicio)}
                  </button>
                ))}
              </div>
            )}

            {slotSelecionado && (
              <div className="selected-schedule field-span-2">
                <Icon name="calendar" size={18} />
                <div>
                  <span>Horário selecionado</span>
                  <strong>
                    {formatTime(slotSelecionado.hora_inicio)} às{" "}
                    {formatTime(slotSelecionado.hora_fim)}
                  </strong>
                </div>
              </div>
            )}
            <label className="field">
              Status
              <select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value as StatusAgendamento })}>
                {statusOptions.map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}
              </select>
            </label>
            <div className="appointment-price-card field-span-2">
              <div>
                <span>Serviço</span>
                <strong>{form.valor_base ? formatCurrency(form.valor_base) : "—"}</strong>
              </div>
              <div>
                <span>
                  Adicional
                  {tipoVeiculoEfetivo
                    ? ` — ${tipoVeiculoLabel(tipoVeiculoEfetivo)}`
                    : ""}
                </span>
                <strong>{form.valor_adicional ? formatCurrency(form.valor_adicional) : "—"}</strong>
              </div>
              <div className="appointment-price-total">
                <span>Valor final</span>
                <strong>{form.valor_final ? formatCurrency(form.valor_final) : "—"}</strong>
              </div>
            </div>
            <label className="field">
              Forma de pagamento
              <select value={form.forma_pagamento} onChange={(event) => setForm({ ...form, forma_pagamento: event.target.value as FormaPagamento | "" })}>
                <option value="">Não informada</option>
                <option value="PIX">PIX</option>
                <option value="DINHEIRO">Dinheiro</option>
                <option value="CARTAO_DEBITO">Cartão de débito</option>
                <option value="CARTAO_CREDITO">Cartão de crédito</option>
                <option value="BOLETO">Boleto</option>
              </select>
            </label>
            <label className="field field-span-2">
              Observações
              <textarea rows={3} value={form.observacoes} onChange={(event) => setForm({ ...form, observacoes: event.target.value })} />
            </label>
          </div>
          <div className="modal-actions">
            <button className="button button-secondary" type="button" onClick={fecharModal}>Cancelar</button>
            <button className="button button-primary" type="submit" disabled={salvando}>
              {salvando ? "Salvando..." : "Salvar agendamento"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
