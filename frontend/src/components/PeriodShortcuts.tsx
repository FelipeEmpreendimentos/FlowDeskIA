import { useState } from "react";
import { todayISO } from "../utils/format";

type PeriodoRapido = "HOJE" | "SEMANA" | "MES";

function deslocarData(dataIso: string, dias: number): string {
  const [ano, mes, dia] = dataIso.split("-").map(Number);
  const data = new Date(ano, mes - 1, dia);
  data.setDate(data.getDate() + dias);
  const local = new Date(data.getTime() - data.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

function primeiroDiaDaSemana(): string {
  const hoje = todayISO();
  const [ano, mes, dia] = hoje.split("-").map(Number);
  const data = new Date(ano, mes - 1, dia);
  const diaSemana = data.getDay();
  return deslocarData(hoje, diaSemana === 0 ? -6 : 1 - diaSemana);
}

function primeiroDiaDoMes(): string {
  return `${todayISO().slice(0, 7)}-01`;
}

export function PeriodShortcuts({
  onChange,
  initialPeriod = "MES",
}: {
  onChange: (dataInicio: string, dataFim: string) => void;
  initialPeriod?: PeriodoRapido;
}) {
  const hoje = todayISO();
  const [selecionado, setSelecionado] =
    useState<PeriodoRapido>(initialPeriod);

  function aplicar(periodo: PeriodoRapido, inicio: string, fim: string) {
    setSelecionado(periodo);
    onChange(inicio, fim);
  }

  return (
    <div className="quick-period-filters" aria-label="Atalhos de período">
      <button
        className={`button button-ghost ${selecionado === "HOJE" ? "quick-period-active" : ""}`}
        type="button"
        onClick={() => aplicar("HOJE", hoje, hoje)}
        aria-pressed={selecionado === "HOJE"}
      >
        Hoje
      </button>
      <button
        className={`button button-ghost ${selecionado === "SEMANA" ? "quick-period-active" : ""}`}
        type="button"
        onClick={() => aplicar("SEMANA", primeiroDiaDaSemana(), hoje)}
        aria-pressed={selecionado === "SEMANA"}
      >
        Esta semana
      </button>
      <button
        className={`button button-ghost ${selecionado === "MES" ? "quick-period-active" : ""}`}
        type="button"
        onClick={() => aplicar("MES", primeiroDiaDoMes(), hoje)}
        aria-pressed={selecionado === "MES"}
      >
        Este mês
      </button>
    </div>
  );
}
