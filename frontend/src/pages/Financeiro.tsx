import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useOutletContext } from "react-router";
import { Icon } from "../components/Icon";
import { Modal } from "../components/Modal";
import { Alert, EmptyState, LoadingState, PageHeader } from "../components/UI";
import { apiRequest, buildQuery } from "../services/api";
import type { AppOutletContext, FormaPagamento } from "../types";
import {
  formatCurrency,
  formatDate,
  formatDateTime,
  todayISO,
} from "../utils/format";

type StatusFechamento =
  | "PENDENTE"
  | "PARCIAL"
  | "PAGO"
  | "CORTESIA"
  | "ESTORNADO";

type TipoDesconto = "VALOR" | "PERCENTUAL";

interface ResumoFinanceiro {
  quantidade: number;
  valor_original: string | number;
  descontos: string | number;
  valor_final: string | number;
  valor_recebido: string | number;
  valor_pendente: string | number;
  pendentes: number;
  parciais: number;
  pagos: number;
  cortesias: number;
}

interface FechamentoListaItem {
  id: number;
  agendamento_id: number;
  data: string;
  hora_inicio: string;
  cliente_id: number;
  cliente_nome: string;
  servico_id: number;
  servico_nome: string;
  funcionario_id: number | null;
  funcionario_nome: string | null;
  valor_original: string | number;
  desconto_valor: string | number;
  valor_final: string | number;
  valor_recebido: string | number;
  valor_pendente: string | number;
  status: StatusFechamento;
  forma_pagamento_principal: FormaPagamento | null;
  fechado_em: string | null;
}

interface Pagamento {
  id: number;
  forma_pagamento: FormaPagamento;
  valor: string | number;
  status: "CONFIRMADO" | "ESTORNADO";
  recebido_em: string;
  observacoes: string | null;
}

interface FechamentoDetalhe {
  id: number;
  agendamento_id: number;
  valor_original: string | number;
  desconto_tipo: TipoDesconto | null;
  desconto_valor: string | number;
  valor_final: string | number;
  valor_recebido: string | number;
  valor_pendente: string | number;
  status: StatusFechamento;
  observacoes: string | null;
  fechado_em: string | null;
  pagamentos: Pagamento[];
}

interface PagamentoForm {
  forma_pagamento: FormaPagamento;
  valor: string;
  observacoes: string;
}

interface AjusteForm {
  desconto_tipo: TipoDesconto | "";
  desconto_valor: string;
  cortesia: boolean;
  observacoes: string;
}

const resumoVazio: ResumoFinanceiro = {
  quantidade: 0,
  valor_original: 0,
  descontos: 0,
  valor_final: 0,
  valor_recebido: 0,
  valor_pendente: 0,
  pendentes: 0,
  parciais: 0,
  pagos: 0,
  cortesias: 0,
};

const formasPagamento: Array<{ value: FormaPagamento; label: string }> = [
  { value: "PIX", label: "PIX" },
  { value: "DINHEIRO", label: "Dinheiro" },
  { value: "CARTAO_DEBITO", label: "Cartão de débito" },
  { value: "CARTAO_CREDITO", label: "Cartão de crédito" },
  { value: "BOLETO", label: "Boleto" },
];

const statusLabels: Record<StatusFechamento, string> = {
  PENDENTE: "Pendente",
  PARCIAL: "Parcial",
  PAGO: "Pago",
  CORTESIA: "Cortesia",
  ESTORNADO: "Estornado",
};

function primeiroDiaDoMes(): string {
  return `${todayISO().slice(0, 7)}-01`;
}

function StatusFinanceiro({ status }: { status: StatusFechamento }) {
  return (
    <span className={`finance-status finance-status-${status.toLowerCase()}`}>
      {statusLabels[status]}
    </span>
  );
}

export function Financeiro() {
  const { usuario } = useOutletContext<AppOutletContext>();
  const [dataInicio, setDataInicio] = useState(primeiroDiaDoMes());
  const [dataFim, setDataFim] = useState(todayISO());
  const [statusFiltro, setStatusFiltro] = useState<StatusFechamento | "">("");
  const [resumo, setResumo] = useState<ResumoFinanceiro>(resumoVazio);
  const [fechamentos, setFechamentos] = useState<FechamentoListaItem[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");

  const [detalhe, setDetalhe] = useState<FechamentoDetalhe | null>(null);
  const [carregandoDetalhe, setCarregandoDetalhe] = useState(false);
  const [modalPagamento, setModalPagamento] = useState(false);
  const [salvandoPagamento, setSalvandoPagamento] = useState(false);
  const [pagamentoForm, setPagamentoForm] = useState<PagamentoForm>({
    forma_pagamento: "PIX",
    valor: "",
    observacoes: "",
  });
  const [modalAjuste, setModalAjuste] = useState(false);
  const [salvandoAjuste, setSalvandoAjuste] = useState(false);
  const [ajusteForm, setAjusteForm] = useState<AjusteForm>({
    desconto_tipo: "",
    desconto_valor: "0",
    cortesia: false,
    observacoes: "",
  });

  const podeAjustar = ["ADMIN", "GERENTE"].includes(usuario.cargo);

  async function carregar() {
    setCarregando(true);
    setErro("");
    try {
      const query = buildQuery({
        data_inicio: dataInicio,
        data_fim: dataFim,
        status_fechamento: statusFiltro,
        limit: 200,
      });
      const resumoQuery = buildQuery({
        data_inicio: dataInicio,
        data_fim: dataFim,
      });
      const [dadosResumo, dadosFechamentos] = await Promise.all([
        apiRequest<ResumoFinanceiro>(`/financeiro/resumo${resumoQuery}`),
        apiRequest<FechamentoListaItem[]>(`/financeiro/fechamentos${query}`),
      ]);
      setResumo(dadosResumo);
      setFechamentos(dadosFechamentos);
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível carregar o financeiro.",
      );
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    void carregar();
  }, [dataInicio, dataFim, statusFiltro]);

  useEffect(() => {
    if (!sucesso) return;
    const timer = window.setTimeout(() => setSucesso(""), 4000);
    return () => window.clearTimeout(timer);
  }, [sucesso]);

  const resumoSituacoes = useMemo(
    () => `${resumo.pagos} pagos · ${resumo.parciais} parciais · ${resumo.pendentes} pendentes`,
    [resumo],
  );

  async function abrirDetalhe(item: FechamentoListaItem) {
    setCarregandoDetalhe(true);
    setErro("");
    try {
      const data = await apiRequest<FechamentoDetalhe>(
        `/financeiro/agendamentos/${item.agendamento_id}/fechamento`,
      );
      setDetalhe(data);
      setAjusteForm({
        desconto_tipo: data.desconto_tipo ?? "",
        desconto_valor: String(data.desconto_valor ?? 0),
        cortesia: data.status === "CORTESIA",
        observacoes: data.observacoes ?? "",
      });
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível carregar o fechamento.",
      );
    } finally {
      setCarregandoDetalhe(false);
    }
  }

  function fecharDetalhe() {
    if (salvandoPagamento || salvandoAjuste) return;
    setDetalhe(null);
    setModalPagamento(false);
    setModalAjuste(false);
  }

  function abrirPagamento(item?: FechamentoListaItem) {
    const pendente = item?.valor_pendente ?? detalhe?.valor_pendente ?? 0;
    setPagamentoForm({
      forma_pagamento: "PIX",
      valor: Number(pendente).toFixed(2),
      observacoes: "",
    });
    setModalPagamento(true);
  }

  async function registrarPagamento(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fechamentoId = detalhe?.id;
    if (!fechamentoId) return;

    setSalvandoPagamento(true);
    setErro("");
    try {
      const atualizado = await apiRequest<FechamentoDetalhe>(
        `/financeiro/fechamentos/${fechamentoId}/pagamentos`,
        {
          method: "POST",
          body: JSON.stringify({
            forma_pagamento: pagamentoForm.forma_pagamento,
            valor: Number(pagamentoForm.valor.replace(",", ".")),
            observacoes: pagamentoForm.observacoes.trim() || null,
          }),
        },
      );
      setDetalhe(atualizado);
      setModalPagamento(false);
      setSucesso("Pagamento registrado com sucesso.");
      await carregar();
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível registrar o pagamento.",
      );
    } finally {
      setSalvandoPagamento(false);
    }
  }

  async function salvarAjuste(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!detalhe) return;

    setSalvandoAjuste(true);
    setErro("");
    try {
      const atualizado = await apiRequest<FechamentoDetalhe>(
        `/financeiro/fechamentos/${detalhe.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            desconto_tipo: ajusteForm.desconto_tipo || null,
            desconto_valor: Number(
              (ajusteForm.desconto_valor || "0").replace(",", "."),
            ),
            cortesia: ajusteForm.cortesia,
            observacoes: ajusteForm.observacoes.trim() || null,
          }),
        },
      );
      setDetalhe(atualizado);
      setModalAjuste(false);
      setSucesso("Fechamento atualizado com sucesso.");
      await carregar();
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível ajustar o fechamento.",
      );
    } finally {
      setSalvandoAjuste(false);
    }
  }

  async function estornarPagamento(pagamento: Pagamento) {
    if (!window.confirm(`Estornar ${formatCurrency(pagamento.valor)}?`)) return;
    setErro("");
    try {
      const atualizado = await apiRequest<FechamentoDetalhe>(
        `/financeiro/pagamentos/${pagamento.id}/estornar`,
        { method: "POST" },
      );
      setDetalhe(atualizado);
      setSucesso("Pagamento estornado.");
      await carregar();
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível estornar o pagamento.",
      );
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Gestão financeira"
        title="Financeiro"
        description="Acompanhe recebimentos, pendências, descontos e pagamentos dos atendimentos."
      />

      {sucesso && <Alert type="success">{sucesso}</Alert>}
      {erro && !modalPagamento && !modalAjuste && <Alert>{erro}</Alert>}

      <section className="finance-metrics-grid">
        <article className="metric-card">
          <span>Valor dos atendimentos</span>
          <strong>{formatCurrency(resumo.valor_final)}</strong>
          <small>{resumo.quantidade} fechamentos no período</small>
        </article>
        <article className="metric-card">
          <span>Recebido</span>
          <strong>{formatCurrency(resumo.valor_recebido)}</strong>
          <small>{resumoSituacoes}</small>
        </article>
        <article className="metric-card">
          <span>Pendente</span>
          <strong>{formatCurrency(resumo.valor_pendente)}</strong>
          <small>A receber de atendimentos finalizados</small>
        </article>
        <article className="metric-card">
          <span>Descontos e cortesias</span>
          <strong>{formatCurrency(resumo.descontos)}</strong>
          <small>{resumo.cortesias} cortesias no período</small>
        </article>
      </section>

      <section className="content-card finance-card">
        <div className="finance-filters">
          <label className="field compact-field">
            Data inicial
            <input
              type="date"
              value={dataInicio}
              max={dataFim}
              onChange={(event) => setDataInicio(event.target.value)}
            />
          </label>
          <label className="field compact-field">
            Data final
            <input
              type="date"
              value={dataFim}
              min={dataInicio}
              onChange={(event) => setDataFim(event.target.value)}
            />
          </label>
          <label className="field compact-field">
            Situação
            <select
              value={statusFiltro}
              onChange={(event) =>
                setStatusFiltro(event.target.value as StatusFechamento | "")
              }
            >
              <option value="">Todas</option>
              <option value="PENDENTE">Pendentes</option>
              <option value="PARCIAL">Parciais</option>
              <option value="PAGO">Pagos</option>
              <option value="CORTESIA">Cortesias</option>
              <option value="ESTORNADO">Estornados</option>
            </select>
          </label>
          <button
            className="button button-secondary finance-refresh"
            type="button"
            onClick={() => void carregar()}
          >
            <Icon name="refresh" size={17} />
            Atualizar
          </button>
        </div>

        {carregando ? (
          <LoadingState label="Carregando financeiro..." />
        ) : fechamentos.length === 0 ? (
          <EmptyState
            icon="finance"
            title="Nenhum fechamento encontrado"
            description="Finalize um atendimento na agenda para iniciar o acompanhamento financeiro."
          />
        ) : (
          <div className="table-wrap">
            <table className="data-table finance-table">
              <thead>
                <tr>
                  <th>Atendimento</th>
                  <th>Cliente</th>
                  <th>Serviço</th>
                  <th>Valor final</th>
                  <th>Recebido</th>
                  <th>Pendente</th>
                  <th>Situação</th>
                  <th className="actions-column">Ações</th>
                </tr>
              </thead>
              <tbody>
                {fechamentos.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <strong className="table-primary">
                        {formatDate(item.data)} · {item.hora_inicio}
                      </strong>
                      <small>Agendamento #{item.agendamento_id}</small>
                    </td>
                    <td>
                      <strong className="table-primary">{item.cliente_nome}</strong>
                      <small>{item.funcionario_nome ?? "Sem responsável"}</small>
                    </td>
                    <td>{item.servico_nome}</td>
                    <td>{formatCurrency(item.valor_final)}</td>
                    <td>{formatCurrency(item.valor_recebido)}</td>
                    <td>
                      <strong className={Number(item.valor_pendente) > 0 ? "finance-pending" : ""}>
                        {formatCurrency(item.valor_pendente)}
                      </strong>
                    </td>
                    <td>
                      <StatusFinanceiro status={item.status} />
                    </td>
                    <td>
                      <div className="row-actions finance-row-actions">
                        <button
                          className="button button-small button-secondary"
                          type="button"
                          onClick={() => void abrirDetalhe(item)}
                          disabled={carregandoDetalhe}
                        >
                          Detalhes
                        </button>
                        {Number(item.valor_pendente) > 0 &&
                          !["CORTESIA", "ESTORNADO"].includes(item.status) && (
                            <button
                              className="button button-small button-primary"
                              type="button"
                              onClick={async () => {
                                await abrirDetalhe(item);
                                abrirPagamento(item);
                              }}
                            >
                              Receber
                            </button>
                          )}
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
        open={Boolean(detalhe) && !modalPagamento && !modalAjuste}
        title={`Fechamento #${detalhe?.id ?? ""}`}
        subtitle={`Agendamento #${detalhe?.agendamento_id ?? ""}`}
        onClose={fecharDetalhe}
        size="large"
      >
        {detalhe && (
          <div className="finance-detail">
            <div className="finance-detail-summary">
              <div>
                <span>Valor original</span>
                <strong>{formatCurrency(detalhe.valor_original)}</strong>
              </div>
              <div>
                <span>Desconto</span>
                <strong>{formatCurrency(detalhe.desconto_valor)}</strong>
              </div>
              <div>
                <span>Valor final</span>
                <strong>{formatCurrency(detalhe.valor_final)}</strong>
              </div>
              <div>
                <span>Recebido</span>
                <strong>{formatCurrency(detalhe.valor_recebido)}</strong>
              </div>
              <div>
                <span>Pendente</span>
                <strong>{formatCurrency(detalhe.valor_pendente)}</strong>
              </div>
              <div>
                <span>Situação</span>
                <StatusFinanceiro status={detalhe.status} />
              </div>
            </div>

            <div className="card-heading finance-detail-heading">
              <div>
                <span>Movimentações</span>
                <h2>Pagamentos</h2>
              </div>
              {Number(detalhe.valor_pendente) > 0 &&
                !["CORTESIA", "ESTORNADO"].includes(detalhe.status) && (
                  <button
                    className="button button-primary button-small"
                    type="button"
                    onClick={() => abrirPagamento()}
                  >
                    <Icon name="plus" size={16} />
                    Registrar pagamento
                  </button>
                )}
            </div>

            {detalhe.pagamentos.length === 0 ? (
              <div className="compact-empty">Nenhum pagamento registrado.</div>
            ) : (
              <div className="finance-payment-list">
                {detalhe.pagamentos.map((pagamento) => (
                  <article
                    className={pagamento.status === "ESTORNADO" ? "finance-payment finance-payment-reversed" : "finance-payment"}
                    key={pagamento.id}
                  >
                    <div>
                      <strong>
                        {formasPagamento.find((item) => item.value === pagamento.forma_pagamento)?.label ?? pagamento.forma_pagamento}
                      </strong>
                      <span>{formatDateTime(pagamento.recebido_em)}</span>
                      {pagamento.observacoes && <small>{pagamento.observacoes}</small>}
                    </div>
                    <strong>{formatCurrency(pagamento.valor)}</strong>
                    {pagamento.status === "ESTORNADO" ? (
                      <span className="finance-reversed-label">Estornado</span>
                    ) : podeAjustar ? (
                      <button
                        className="button button-small button-danger"
                        type="button"
                        onClick={() => void estornarPagamento(pagamento)}
                      >
                        Estornar
                      </button>
                    ) : null}
                  </article>
                ))}
              </div>
            )}

            {detalhe.observacoes && (
              <div className="finance-notes">
                <strong>Observações</strong>
                <p>{detalhe.observacoes}</p>
              </div>
            )}

            <div className="modal-actions">
              {podeAjustar && (
                <button
                  className="button button-secondary"
                  type="button"
                  onClick={() => setModalAjuste(true)}
                >
                  Ajustar fechamento
                </button>
              )}
              <button className="button button-primary" type="button" onClick={fecharDetalhe}>
                Fechar
              </button>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        open={modalPagamento}
        title="Registrar pagamento"
        subtitle={`Saldo pendente: ${formatCurrency(detalhe?.valor_pendente)}`}
        onClose={() => setModalPagamento(false)}
        size="small"
      >
        <form onSubmit={registrarPagamento}>
          {erro && <Alert>{erro}</Alert>}
          <div className="form-grid">
            <label className="field">
              Forma de pagamento
              <select
                value={pagamentoForm.forma_pagamento}
                onChange={(event) =>
                  setPagamentoForm({
                    ...pagamentoForm,
                    forma_pagamento: event.target.value as FormaPagamento,
                  })
                }
              >
                {formasPagamento.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              Valor recebido
              <input
                type="number"
                min="0.01"
                step="0.01"
                max={Number(detalhe?.valor_pendente ?? 0)}
                value={pagamentoForm.valor}
                onChange={(event) =>
                  setPagamentoForm({ ...pagamentoForm, valor: event.target.value })
                }
                required
              />
            </label>
            <label className="field">
              Observações
              <textarea
                rows={3}
                value={pagamentoForm.observacoes}
                onChange={(event) =>
                  setPagamentoForm({
                    ...pagamentoForm,
                    observacoes: event.target.value,
                  })
                }
              />
            </label>
          </div>
          <div className="modal-actions">
            <button
              className="button button-secondary"
              type="button"
              onClick={() => setModalPagamento(false)}
              disabled={salvandoPagamento}
            >
              Cancelar
            </button>
            <button
              className="button button-primary"
              type="submit"
              disabled={salvandoPagamento}
            >
              {salvandoPagamento ? "Registrando..." : "Registrar pagamento"}
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        open={modalAjuste}
        title="Ajustar fechamento"
        subtitle="Descontos e cortesias ficam registrados no histórico."
        onClose={() => setModalAjuste(false)}
        size="small"
      >
        <form onSubmit={salvarAjuste}>
          {erro && <Alert>{erro}</Alert>}
          <div className="form-grid">
            <label className="checkbox-field finance-courtesy-field">
              <input
                type="checkbox"
                checked={ajusteForm.cortesia}
                onChange={(event) =>
                  setAjusteForm({
                    ...ajusteForm,
                    cortesia: event.target.checked,
                  })
                }
              />
              Marcar atendimento como cortesia
            </label>
            {!ajusteForm.cortesia && (
              <>
                <label className="field">
                  Tipo de desconto
                  <select
                    value={ajusteForm.desconto_tipo}
                    onChange={(event) =>
                      setAjusteForm({
                        ...ajusteForm,
                        desconto_tipo: event.target.value as TipoDesconto | "",
                        desconto_valor: event.target.value ? ajusteForm.desconto_valor : "0",
                      })
                    }
                  >
                    <option value="">Sem desconto</option>
                    <option value="VALOR">Valor em reais</option>
                    <option value="PERCENTUAL">Porcentagem</option>
                  </select>
                </label>
                {ajusteForm.desconto_tipo && (
                  <label className="field">
                    {ajusteForm.desconto_tipo === "PERCENTUAL"
                      ? "Percentual de desconto"
                      : "Valor do desconto"}
                    <input
                      type="number"
                      min="0"
                      max={
                        ajusteForm.desconto_tipo === "PERCENTUAL"
                          ? 100
                          : Number(detalhe?.valor_original ?? 0)
                      }
                      step="0.01"
                      value={ajusteForm.desconto_valor}
                      onChange={(event) =>
                        setAjusteForm({
                          ...ajusteForm,
                          desconto_valor: event.target.value,
                        })
                      }
                    />
                  </label>
                )}
              </>
            )}
            <label className="field">
              Observações
              <textarea
                rows={4}
                value={ajusteForm.observacoes}
                onChange={(event) =>
                  setAjusteForm({
                    ...ajusteForm,
                    observacoes: event.target.value,
                  })
                }
              />
            </label>
          </div>
          <div className="modal-actions">
            <button
              className="button button-secondary"
              type="button"
              onClick={() => setModalAjuste(false)}
              disabled={salvandoAjuste}
            >
              Cancelar
            </button>
            <button
              className="button button-primary"
              type="submit"
              disabled={salvandoAjuste}
            >
              {salvandoAjuste ? "Salvando..." : "Salvar ajuste"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
