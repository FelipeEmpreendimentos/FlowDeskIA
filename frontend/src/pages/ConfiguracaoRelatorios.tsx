import { useEffect, useState } from "react";
import { Icon } from "../components/Icon";
import { Alert, LoadingState, PageHeader } from "../components/UI";
import { apiRequest } from "../services/api";
import { showAppToast } from "../services/feedback";
import {
  applyReportFinanceVisibility,
  type ReportSettings,
} from "../services/reportSettings";

export function ConfiguracaoRelatorios() {
  const [usarFinanceiro, setUsarFinanceiro] = useState(true);
  const [valorSalvo, setValorSalvo] = useState(true);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");

  useEffect(() => {
    async function carregar() {
      setCarregando(true);
      setErro("");
      try {
        const data = await apiRequest<ReportSettings>(
          "/configuracoes/relatorios",
        );
        setUsarFinanceiro(data.usar_financeiro);
        setValorSalvo(data.usar_financeiro);
        applyReportFinanceVisibility(data.usar_financeiro);
      } catch (error) {
        setErro(
          error instanceof Error
            ? error.message
            : "Não foi possível carregar a configuração dos relatórios.",
        );
      } finally {
        setCarregando(false);
      }
    }

    void carregar();
  }, []);

  async function salvar() {
    setSalvando(true);
    setErro("");
    try {
      const data = await apiRequest<ReportSettings>(
        "/configuracoes/relatorios",
        {
          method: "PUT",
          body: JSON.stringify({ usar_financeiro: usarFinanceiro }),
        },
      );
      setUsarFinanceiro(data.usar_financeiro);
      setValorSalvo(data.usar_financeiro);
      applyReportFinanceVisibility(data.usar_financeiro);
      showAppToast("Origem do faturamento dos relatórios atualizada com sucesso.");
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível salvar a configuração dos relatórios.",
      );
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="page report-settings-page">
      <PageHeader
        eyebrow="Configuração administrativa"
        title="Relatórios e financeiro"
        description="Defina de onde o FlowDeskIA deve calcular o faturamento exibido nos relatórios."
      />

      {erro && <Alert>{erro}</Alert>}

      {carregando ? (
        <section className="content-card">
          <LoadingState label="Carregando configuração..." />
        </section>
      ) : (
        <section className="content-card report-source-card">
          <div className="card-heading">
            <div>
              <span>Origem do faturamento</span>
              <h2>Como alimentar os relatórios</h2>
            </div>
            <Icon name="dashboard" size={24} />
          </div>

          <p className="report-source-intro">
            Escolha uma única fonte. A alteração não apaga agendamentos nem
            registros financeiros existentes; ela muda somente como os relatórios
            calculam os valores.
          </p>

          <div
            className="report-source-options"
            role="radiogroup"
            aria-label="Origem do faturamento"
          >
            <button
              className={`report-source-option ${usarFinanceiro ? "active" : ""}`}
              type="button"
              role="radio"
              aria-checked={usarFinanceiro}
              onClick={() => setUsarFinanceiro(true)}
            >
              <span className="report-source-icon">
                <Icon name="finance" size={21} />
              </span>
              <span className="report-source-copy">
                <strong>Financeiro do FlowDeskIA</strong>
                <small>
                  Mantém o comportamento atual. Faturamento, recebimentos,
                  pendências e descontos vêm dos registros do Financeiro.
                </small>
              </span>
              <span className="report-source-radio" aria-hidden="true" />
            </button>

            <button
              className={`report-source-option ${!usarFinanceiro ? "active" : ""}`}
              type="button"
              role="radio"
              aria-checked={!usarFinanceiro}
              onClick={() => setUsarFinanceiro(false)}
            >
              <span className="report-source-icon">
                <Icon name="calendar" size={21} />
              </span>
              <span className="report-source-copy">
                <strong>Agendamentos finalizados</strong>
                <small>
                  O valor do atendimento entra no relatório assim que o agendamento
                  é finalizado. O módulo Financeiro pode permanecer desativado.
                </small>
              </span>
              <span className="report-source-radio" aria-hidden="true" />
            </button>
          </div>

          {!usarFinanceiro && (
            <div className="report-source-note">
              <span className="report-source-note-icon">
                <Icon name="check" size={16} />
              </span>
              <span className="report-source-note-copy">
                <strong>Relatórios pela Agenda</strong>
                <small>
                  Só atendimentos finalizados entram no faturamento. O FlowDeskIA
                  considera automaticamente o valor final de cada agendamento.
                </small>
              </span>
            </div>
          )}

          <div className="form-footer report-source-footer">
            <button
              className="button button-primary"
              type="button"
              onClick={() => void salvar()}
              disabled={salvando || usarFinanceiro === valorSalvo}
            >
              {salvando ? "Salvando..." : "Salvar configuração"}
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
