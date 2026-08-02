import { todayISO } from "../utils/format";

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
}: {
  onChange: (dataInicio: string, dataFim: string) => void;
}) {
  const hoje = todayISO();

  return (
    <div className="quick-period-filters" aria-label="Atalhos de período">
      <button
        className="button button-ghost"
        type="button"
        onClick={() => onChange(hoje, hoje)}
      >
        Hoje
      </button>
      <button
        className="button button-ghost"
        type="button"
        onClick={() => onChange(primeiroDiaDaSemana(), hoje)}
      >
        Esta semana
      </button>
      <button
        className="button button-ghost"
        type="button"
        onClick={() => onChange(primeiroDiaDoMes(), hoje)}
      >
        Este mês
      </button>
    </div>
  );
}
