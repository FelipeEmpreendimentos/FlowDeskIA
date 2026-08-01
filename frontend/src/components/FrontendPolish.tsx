import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation } from "react-router";
import { Icon } from "./Icon";

interface ConfirmacaoPendente {
  elemento: HTMLButtonElement;
  titulo: string;
  descricao: string;
  acao: string;
}

type PeriodoRapido = "hoje" | "semana" | "mes";

function formatarData(data: Date): string {
  const local = new Date(data.getTime() - data.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

function intervalo(periodo: PeriodoRapido): [string, string] {
  const hoje = new Date();
  const fim = formatarData(hoje);

  if (periodo === "hoje") return [fim, fim];

  const inicio = new Date(hoje);
  if (periodo === "semana") {
    const dia = inicio.getDay();
    inicio.setDate(inicio.getDate() + (dia === 0 ? -6 : 1 - dia));
  } else {
    inicio.setDate(1);
  }

  return [formatarData(inicio), fim];
}

function atualizarInput(input: HTMLInputElement, valor: string) {
  const setter = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype,
    "value",
  )?.set;
  setter?.call(input, valor);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

function FiltroPeriodoRapido({ host }: { host: HTMLElement }) {
  const [ativo, setAtivo] = useState<PeriodoRapido | null>(null);

  function aplicar(periodo: PeriodoRapido) {
    const filtros = host.parentElement;
    const inputs = filtros?.querySelectorAll<HTMLInputElement>('input[type="date"]');
    if (!inputs || inputs.length < 2) return;

    const [inicio, fim] = intervalo(periodo);
    atualizarInput(inputs[0], inicio);
    atualizarInput(inputs[1], fim);
    setAtivo(periodo);
  }

  return createPortal(
    <div className="quick-period-filter" aria-label="Filtro rápido de período">
      <button
        className={ativo === "hoje" ? "quick-period-active" : ""}
        type="button"
        onClick={() => aplicar("hoje")}
      >
        Hoje
      </button>
      <button
        className={ativo === "semana" ? "quick-period-active" : ""}
        type="button"
        onClick={() => aplicar("semana")}
      >
        Esta semana
      </button>
      <button
        className={ativo === "mes" ? "quick-period-active" : ""}
        type="button"
        onClick={() => aplicar("mes")}
      >
        Este mês
      </button>
    </div>,
    host,
  );
}

export function FrontendPolish() {
  const location = useLocation();
  const [confirmacao, setConfirmacao] = useState<ConfirmacaoPendente | null>(null);
  const [hostPeriodo, setHostPeriodo] = useState<HTMLElement | null>(null);
  const ignorarClique = useMemo(() => new WeakSet<HTMLButtonElement>(), []);

  useEffect(() => {
    setConfirmacao(null);
    setHostPeriodo(null);

    function prepararFiltroRapido() {
      const seletor = location.pathname === "/financeiro"
        ? ".finance-filters"
        : location.pathname === "/relatorios"
          ? ".report-filters"
          : null;

      if (!seletor) return;
      const filtros = document.querySelector<HTMLElement>(seletor);
      if (!filtros) return;

      let host = filtros.querySelector<HTMLElement>(".quick-period-filter-host");
      if (!host) {
        host = document.createElement("div");
        host.className = "quick-period-filter-host";
        const atualizar = Array.from(filtros.children).find((item) =>
          item.textContent?.includes("Atualizar"),
        );
        filtros.insertBefore(host, atualizar ?? null);
      }
      setHostPeriodo(host);
    }

    prepararFiltroRapido();
    const observer = new MutationObserver(prepararFiltroRapido);
    observer.observe(document.body, { childList: true, subtree: true });

    function interceptar(event: MouseEvent) {
      const botao = (event.target as Element | null)?.closest<HTMLButtonElement>("button");
      if (!botao || ignorarClique.has(botao)) return;

      const titulo = botao.getAttribute("title") ?? "";
      const emAgenda = location.pathname === "/agenda" && titulo === "Cancelar";
      const emVeiculos = location.pathname === "/veiculos" && titulo === "Excluir veículo";
      if (!emAgenda && !emVeiculos) return;

      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();

      const card = botao.closest("article, tr");
      const nome = card?.querySelector("h3, strong")?.textContent?.trim();
      setConfirmacao({
        elemento: botao,
        titulo: emAgenda ? "Cancelar agendamento" : "Excluir veículo",
        descricao: emAgenda
          ? `Tem certeza que deseja cancelar${nome ? ` o agendamento de ${nome}` : " este agendamento"}? O horário será liberado e o registro continuará no histórico.`
          : `Tem certeza que deseja excluir${nome ? ` o veículo ${nome}` : " este veículo"}? Esta ação não poderá ser desfeita.`,
        acao: emAgenda ? "Cancelar agendamento" : "Excluir veículo",
      });
    }

    document.addEventListener("click", interceptar, true);
    return () => {
      observer.disconnect();
      document.removeEventListener("click", interceptar, true);
    };
  }, [ignorarClique, location.pathname]);

  function confirmar() {
    if (!confirmacao) return;
    const botao = confirmacao.elemento;
    setConfirmacao(null);
    ignorarClique.add(botao);

    const confirmOriginal = window.confirm;
    window.confirm = () => true;
    botao.click();
    window.setTimeout(() => {
      window.confirm = confirmOriginal;
      ignorarClique.delete(botao);
    }, 0);
  }

  return (
    <>
      {hostPeriodo && <FiltroPeriodoRapido host={hostPeriodo} />}

      {confirmacao &&
        createPortal(
          <div className="polish-confirm-overlay" role="presentation">
            <section
              className="polish-confirm-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="polish-confirm-title"
            >
              <button
                className="polish-confirm-close"
                type="button"
                onClick={() => setConfirmacao(null)}
                aria-label="Fechar"
              >
                <Icon name="close" size={18} />
              </button>
              <span className="polish-confirm-icon">
                <Icon name="trash" size={24} />
              </span>
              <div>
                <h2 id="polish-confirm-title">{confirmacao.titulo}</h2>
                <p>{confirmacao.descricao}</p>
              </div>
              <footer>
                <button
                  className="button button-secondary"
                  type="button"
                  onClick={() => setConfirmacao(null)}
                >
                  Voltar
                </button>
                <button className="button button-danger" type="button" onClick={confirmar}>
                  {confirmacao.acao}
                </button>
              </footer>
            </section>
          </div>,
          document.body,
        )}
    </>
  );
}
