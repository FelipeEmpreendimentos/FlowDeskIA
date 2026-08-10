import { useEffect, useMemo, useState } from "react";
import { Icon } from "../components/Icon";
import { PeriodShortcuts } from "../components/PeriodShortcuts";
import { Alert, EmptyState, LoadingState, PageHeader } from "../components/UI";
import { ApiError, apiRequest, buildQuery } from "../services/api";
import { formatCurrency, formatDateTime, todayISO } from "../utils/format";

type AbaRelatorio = "resumo" | "servicos" | "equipe" | "avaliacoes";

interface Resumo {
  data_inicio: string;
  data_fim: string;
  usar_financeiro: boolean;
  atendimentos: number;
  faturamento: string | number;
  recebido: string | number;
  pendente: string | number;
  descontos: string | number;
  ticket_medio: string | number;
  cancelamentos: number;
  clientes_novos: number;
  clientes_recorrentes: number;
}

interface EvolucaoItem {
  data: string;
  atendimentos: number;
  faturamento: string | number;
  recebido: string | number;
  pendente: string | number;
}

interface ServicoItem {
  servico_id: number;
  servico_nome: string;
  atendimentos: number;
  faturamento: string | number;
  recebido: string | number;
  ticket_medio: string | number;
}

interface FuncionarioItem {
  funcionario_id: number | null;
  funcionario_nome: string;
  atendimentos: number;
  faturamento: string | number;
  recebido: string | number;
  ticket_medio: string | number;
}

interface AvaliacaoComentario {
  conversa_id: number;
  cliente_id: number;
  cliente_nome: string;
  funcionario_id: number | null;
  funcionario_nome: string | null;
  nota: number;
  comentario: string | null;
  respondida_em: string | null;
}

interface Avaliacoes {
  quantidade: number;
  media: string | number;
  notas: Record<string, number>;
  avaliacoes_baixas: number;
  comentarios: AvaliacaoComentario[];
}

const resumoVazio: Resumo = {
  data_inicio: todayISO(),
  data_fim: todayISO(),
  usar_financeiro: true,
  atendimentos: 0,
  faturamento: 0,
  recebido: 0,
  pendente: 0,
  descontos: 0,
  ticket_medio: 0,
  cancelamentos: 0,
  clientes_novos: 0,
  clientes_recorrentes: 0,
};

const avaliacoesVazias: Avaliacoes = {
  quantidade: 0,
  media: 0,
  notas: { "1": 0, "2": 0, "3": 0, "4": 0, "5": 0 },
  avaliacoes_baixas: 0,
  comentarios: [],
};

const coresGrafico = ["#3157d5", "#14a37f", "#e39b16", "#8a5bd6", "#e25d6f", "#8b96a8"];

function primeiroDiaDoMes() {
  return `${todayISO().slice(0, 7)}-01`;
}

function estrelas(nota: number): string {
  return `${"★".repeat(Math.max(0, Math.min(5, nota)))}${"☆".repeat(Math.max(0, 5 - nota))}`;
}

function dataCurta(dataIso: string): string {
  const [ano, mes, dia] = dataIso.split("-").map(Number);
  return new Date(ano, mes - 1, dia).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
  });
}

function GraficoEvolucao({
  dados,
  usarFinanceiro,
}: {
  dados: EvolucaoItem[];
  usarFinanceiro: boolean;
}) {
  const largura = 760;
  const altura = 270;
  const margem = { top: 24, right: 22, bottom: 42, left: 62 };
  const areaLargura = largura - margem.left - margem.right;
  const areaAltura = altura - margem.top - margem.bottom;
  const maiorValor = Math.max(
    1,
    ...dados.flatMap((item) =>
      usarFinanceiro
        ? [Number(item.faturamento), Number(item.recebido)]
        : [Number(item.faturamento)],
    ),
  );
  const passoX = dados.length > 1 ? areaLargura / (dados.length - 1) : areaLargura;

  function pontos(chave: "faturamento" | "recebido") {
    return dados
      .map((item, index) => {
        const x = margem.left + index * passoX;
        const y = margem.top + areaAltura - (Number(item[chave]) / maiorValor) * areaAltura;
        return `${x},${y}`;
      })
      .join(" ");
  }

  const indicesRotulos = Array.from(
    new Set([0, Math.floor((dados.length - 1) / 2), Math.max(0, dados.length - 1)]),
  );

  return (
    <article className="content-card report-chart-card report-line-card">
      <div className="card-heading">
        <div>
          <span>Evolução no período</span>
          <h2>
            {usarFinanceiro
              ? "Faturamento e recebimentos"
              : "Faturamento dos atendimentos finalizados"}
          </h2>
        </div>
        <div className="report-chart-legend">
          <span><i className="legend-billed" />Faturamento</span>
          {usarFinanceiro && <span><i className="legend-received" />Recebido</span>}
        </div>
      </div>

      {dados.length === 0 ? (
        <div className="compact-empty">Sem dados para montar o gráfico.</div>
      ) : (
        <div className="report-line-chart" role="img" aria-label="Evolução do faturamento">
          <svg viewBox={`0 0 ${largura} ${altura}`} preserveAspectRatio="none">
            {[0, 0.25, 0.5, 0.75, 1].map((parte) => {
              const y = margem.top + areaAltura - parte * areaAltura;
              return (
                <g key={parte}>
                  <line
                    className="report-grid-line"
                    x1={margem.left}
                    x2={largura - margem.right}
                    y1={y}
                    y2={y}
                  />
                  <text className="report-axis-label" x={margem.left - 10} y={y + 4} textAnchor="end">
                    {formatCurrency(maiorValor * parte)}
                  </text>
                </g>
              );
            })}

            <polyline className="report-line report-line-billed" points={pontos("faturamento")} />
            {usarFinanceiro && (
              <polyline className="report-line report-line-received" points={pontos("recebido")} />
            )}

            {indicesRotulos.map((index) => {
              const item = dados[index];
              if (!item) return null;
              const x = margem.left + index * passoX;
              return (
                <text
                  className="report-axis-label report-date-label"
                  key={`${item.data}-${index}`}
                  x={x}
                  y={altura - 12}
                  textAnchor={index === 0 ? "start" : index === dados.length - 1 ? "end" : "middle"}
                >
                  {dataCurta(item.data)}
                </text>
              );
            })}
          </svg>
        </div>
      )}
    </article>
  );
}

function GraficoServicos({ servicos }: { servicos: ServicoItem[] }) {
  const itens = useMemo(() => {
    const ordenados = [...servicos]
      .filter((item) => Number(item.faturamento) > 0)
      .sort((a, b) => Number(b.faturamento) - Number(a.faturamento));
    const principais = ordenados.slice(0, 5).map((item) => ({
      nome: item.servico_nome,
      valor: Number(item.faturamento),
    }));
    const outros = ordenados.slice(5).reduce((total, item) => total + Number(item.faturamento), 0);
    if (outros > 0) principais.push({ nome: "Outros", valor: outros });
    return principais;
  }, [servicos]);

  const total = itens.reduce((soma, item) => soma + item.valor, 0);
  let acumulado = 0;
  const gradiente = itens
    .map((item, index) => {
      const inicio = total > 0 ? (acumulado / total) * 100 : 0;
      acumulado += item.valor;
      const fim = total > 0 ? (acumulado / total) * 100 : 0;
      return `${coresGrafico[index % coresGrafico.length]} ${inicio}% ${fim}%`;
    })
    .join(", ");

  return (
    <article className="content-card report-chart-card report-donut-card">
      <div className="card-heading">
        <div>
          <span>Distribuição</span>
          <h2>Faturamento por serviço</h2>
        </div>
      </div>

      {total <= 0 ? (
        <div className="compact-empty">Finalize atendimentos para visualizar a distribuição.</div>
      ) : (
        <div className="report-donut-content">
          <div
            className="report-donut"
            style={{ background: `conic-gradient(${gradiente})` }}
            role="img"
            aria-label="Distribuição do faturamento por serviço"
          >
            <div>
              <span>Total</span>
              <strong>{formatCurrency(total)}</strong>
            </div>
          </div>
          <div className="report-donut-legend">
            {itens.map((item, index) => (
              <div key={item.nome}>
                <i style={{ background: coresGrafico[index % coresGrafico.length] }} />
                <span>{item.nome}</span>
                <strong>{Math.round((item.valor / total) * 100)}%</strong>
              </div>
            ))}
          </div>
        </div>
      )}
    </article>
  );
}

export function Relatorios() {
  const [aba, setAba] = useState<AbaRelatorio>("resumo");
  const [dataInicio, setDataInicio] = useState(primeiroDiaDoMes());
  const [dataFim, setDataFim] = useState(todayISO());
  const [resumo, setResumo] = useState<Resumo>(resumoVazio);
  const [evolucao, setEvolucao] = useState<EvolucaoItem[]>([]);
  const [servicos, setServicos] = useState<ServicoItem[]>([]);
  const [funcionarios, setFuncionarios] = useState<FuncionarioItem[]>([]);
  const [avaliacoes, setAvaliacoes] = useState<Avaliacoes>(avaliacoesVazias);
  const [avaliacoesBloqueadas, setAvaliacoesBloqueadas] = useState(false);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");

  async function carregar() {
    setCarregando(true);
    setErro("");
    const query = buildQuery({ data_inicio: dataInicio, data_fim: dataFim });
    try {
      const [dadosResumo, dadosEvolucao, dadosServicos, dadosFuncionarios] = await Promise.all([
        apiRequest<Resumo>(`/relatorios/resumo${query}`),
        apiRequest<EvolucaoItem[]>(`/relatorios/evolucao${query}`),
        apiRequest<ServicoItem[]>(`/relatorios/servicos${query}`),
        apiRequest<FuncionarioItem[]>(`/relatorios/funcionarios${query}`),
      ]);
      setResumo(dadosResumo);
      setEvolucao(dadosEvolucao);
      setServicos(dadosServicos);
      setFuncionarios(dadosFuncionarios);

      try {
        const dadosAvaliacoes = await apiRequest<Avaliacoes>(
          `/relatorios/avaliacoes${query}`,
        );
        setAvaliacoes(dadosAvaliacoes);
        setAvaliacoesBloqueadas(false);
      } catch (error) {
        if (error instanceof ApiError && error.status === 403) {
          setAvaliacoes(avaliacoesVazias);
          setAvaliacoesBloqueadas(true);
        } else {
          throw error;
        }
      }
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível carregar os relatórios.",
      );
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    void carregar();
  }, [dataInicio, dataFim]);

  const maiorNota = useMemo(
    () => Math.max(1, ...Object.values(avaliacoes.notas)),
    [avaliacoes.notas],
  );

  function alterarPeriodo(inicio: string, fim: string) {
    setDataInicio(inicio);
    setDataFim(fim);
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Indicadores"
        title="Relatórios"
        description="Acompanhe faturamento, atendimentos, equipe e satisfação dos clientes."
      />

      {erro && <Alert>{erro}</Alert>}

      <section className="content-card report-filter-card">
        <div className="report-filters">
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
          <PeriodShortcuts onChange={alterarPeriodo} />
          <button
            className="button button-secondary report-refresh"
            type="button"
            onClick={() => void carregar()}
          >
            <Icon name="refresh" size={17} />
            Atualizar
          </button>
        </div>
      </section>

      {!resumo.usar_financeiro && !carregando && (
        <div className="report-source-runtime-note">
          <Icon name="calendar" size={16} />
          Faturamento calculado diretamente pelos agendamentos finalizados.
        </div>
      )}

      <div className="tabs report-tabs">
        <button className={aba === "resumo" ? "tab-active" : ""} type="button" onClick={() => setAba("resumo")}>Visão geral</button>
        <button className={aba === "servicos" ? "tab-active" : ""} type="button" onClick={() => setAba("servicos")}>Serviços</button>
        <button className={aba === "equipe" ? "tab-active" : ""} type="button" onClick={() => setAba("equipe")}>Equipe</button>
        <button className={aba === "avaliacoes" ? "tab-active" : ""} type="button" onClick={() => setAba("avaliacoes")}>Avaliações</button>
      </div>

      {carregando ? (
        <LoadingState label="Calculando relatórios..." />
      ) : aba === "resumo" ? (
        <>
          <section className="report-metrics-grid">
            <article className="metric-card"><span>Faturamento</span><strong>{formatCurrency(resumo.faturamento)}</strong><small>{resumo.atendimentos} atendimentos</small></article>
            {resumo.usar_financeiro ? (
              <article className="metric-card"><span>Valor recebido</span><strong>{formatCurrency(resumo.recebido)}</strong><small>{formatCurrency(resumo.pendente)} pendente</small></article>
            ) : (
              <article className="metric-card"><span>Origem</span><strong>Agendamentos</strong><small>Somente atendimentos finalizados</small></article>
            )}
            <article className="metric-card"><span>Ticket médio</span><strong>{formatCurrency(resumo.ticket_medio)}</strong><small>{resumo.usar_financeiro ? `${formatCurrency(resumo.descontos)} em descontos` : "Sem depender de recebimentos"}</small></article>
            <article className="metric-card"><span>Clientes recorrentes</span><strong>{resumo.clientes_recorrentes}</strong><small>{resumo.clientes_novos} clientes novos</small></article>
          </section>

          <section className="report-charts-grid">
            <GraficoEvolucao dados={evolucao} usarFinanceiro={resumo.usar_financeiro} />
            <GraficoServicos servicos={servicos} />
          </section>

          <section className="report-summary-grid">
            <article className="content-card report-highlight"><span>Eficiência operacional</span><strong>{resumo.atendimentos}</strong><p>Atendimentos finalizados e contabilizados no período.</p></article>
            <article className="content-card report-highlight"><span>Cancelamentos</span><strong>{resumo.cancelamentos}</strong><p>Agendamentos cancelados entre as datas selecionadas.</p></article>
            {resumo.usar_financeiro ? (
              <article className="content-card report-highlight"><span>Saldo a receber</span><strong>{formatCurrency(resumo.pendente)}</strong><p>Valores parciais ou ainda não pagos.</p></article>
            ) : (
              <article className="content-card report-highlight"><span>Regra de faturamento</span><strong>Finalizado</strong><p>O valor entra no relatório quando o atendimento é finalizado na Agenda.</p></article>
            )}
          </section>
        </>
      ) : aba === "servicos" ? (
        <section className="content-card">
          <div className="card-heading"><div><span>Desempenho comercial</span><h2>Serviços no período</h2></div></div>
          {servicos.length === 0 ? (
            <EmptyState icon="services" title="Sem dados de serviços" description="Finalize atendimentos para alimentar este relatório." />
          ) : (
            <div className="table-wrap"><table className="data-table report-table"><thead><tr><th>Serviço</th><th>Atendimentos</th><th>Faturamento</th>{resumo.usar_financeiro && <th>Recebido</th>}<th>Ticket médio</th></tr></thead><tbody>
              {servicos.map((item) => <tr key={item.servico_id}><td><strong className="table-primary">{item.servico_nome}</strong></td><td>{item.atendimentos}</td><td>{formatCurrency(item.faturamento)}</td>{resumo.usar_financeiro && <td>{formatCurrency(item.recebido)}</td>}<td>{formatCurrency(item.ticket_medio)}</td></tr>)}
            </tbody></table></div>
          )}
        </section>
      ) : aba === "equipe" ? (
        <section className="content-card">
          <div className="card-heading"><div><span>Operação</span><h2>Desempenho por funcionário</h2></div></div>
          {funcionarios.length === 0 ? (
            <EmptyState icon="team" title="Sem dados da equipe" description="Os resultados aparecem após os primeiros atendimentos finalizados." />
          ) : (
            <div className="table-wrap"><table className="data-table report-table"><thead><tr><th>Funcionário</th><th>Atendimentos</th><th>Faturamento</th>{resumo.usar_financeiro && <th>Recebido</th>}<th>Ticket médio</th></tr></thead><tbody>
              {funcionarios.map((item) => <tr key={item.funcionario_id ?? "sem-responsavel"}><td><strong className="table-primary">{item.funcionario_nome}</strong></td><td>{item.atendimentos}</td><td>{formatCurrency(item.faturamento)}</td>{resumo.usar_financeiro && <td>{formatCurrency(item.recebido)}</td>}<td>{formatCurrency(item.ticket_medio)}</td></tr>)}
            </tbody></table></div>
          )}
        </section>
      ) : avaliacoesBloqueadas ? (
        <section className="content-card"><EmptyState icon="lock" title="Avaliações não incluídas no plano" description="O relatório geral continua disponível. A área de avaliações pode ser liberada pelo Super Admin." /></section>
      ) : (
        <div className="report-evaluation-grid">
          <section className="content-card evaluation-overview">
            <div className="evaluation-score"><span>Nota média</span><strong>{Number(avaliacoes.media).toFixed(1)}</strong><p>{estrelas(Math.round(Number(avaliacoes.media)))}</p><small>{avaliacoes.quantidade} avaliações</small></div>
            <div className="evaluation-distribution">
              {[5, 4, 3, 2, 1].map((nota) => <div key={nota}><span>{nota} ★</span><div><i style={{ width: `${(Number(avaliacoes.notas[String(nota)] ?? 0) / maiorNota) * 100}%` }} /></div><strong>{avaliacoes.notas[String(nota)] ?? 0}</strong></div>)}
            </div>
            <div className="evaluation-warning"><strong>{avaliacoes.avaliacoes_baixas}</strong><span>Avaliações com 1 ou 2 estrelas</span></div>
          </section>

          <section className="content-card evaluation-comments-card">
            <div className="card-heading"><div><span>Experiência do cliente</span><h2>Avaliações recentes</h2></div></div>
            {avaliacoes.comentarios.length === 0 ? (
              <div className="compact-empty">Nenhuma avaliação respondida no período.</div>
            ) : (
              <div className="evaluation-comments">
                {avaliacoes.comentarios.map((item) => <article key={item.conversa_id}><div><strong>{item.cliente_nome}</strong><span>{estrelas(item.nota)}</span></div><p>{item.comentario || "Cliente avaliou sem deixar comentário."}</p><small>{item.funcionario_nome || "Sem responsável"} · {formatDateTime(item.respondida_em)}</small></article>)}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
