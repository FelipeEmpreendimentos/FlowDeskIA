import { useEffect, useMemo, useState } from "react";
import { Alert, EmptyState, LoadingState, PageHeader, StatusBadge } from "../components/UI";
import { apiRequest } from "../services/api";
import { formatCurrency, formatDate } from "../utils/format";

interface ConsumoItem {
  chave: string;
  nome: string;
  utilizado: number;
  limite: number | null;
}

interface PlanoAtual {
  plano_id: number | null;
  plano_nome: string | null;
  descricao: string | null;
  preco_mensal: string | number | null;
  preco_anual: string | number | null;
  status_empresa: string | null;
  status_assinatura: string | null;
  trial_fim: string | null;
  data_inicio: string | null;
  data_vencimento: string | null;
  ia_ativa: boolean;
  ia_adicional_ativo: boolean;
  recursos: Record<string, boolean>;
  consumo: ConsumoItem[];
}

const recursoLabels: Record<string, string> = {
  AGENDA: "Agenda",
  CLIENTES: "Clientes",
  VEICULOS: "Veículos",
  SERVICOS: "Serviços",
  CONVERSAS: "Conversas",
  NOTIFICACOES: "Notificações",
  WHATSAPP: "WhatsApp",
  INSTAGRAM: "Instagram",
  INTELIGENCIA_ARTIFICIAL: "Inteligência artificial",
  AVALIACOES: "Avaliações",
  RELATORIOS: "Relatórios",
  AUTOMACOES: "Automações",
  MULTIPLAS_UNIDADES: "Múltiplas unidades",
  SUPORTE_PRIORITARIO: "Suporte prioritário",
};

function percentual(item: ConsumoItem): number {
  if (item.limite === null || item.limite <= 0) return 0;
  return Math.min(100, Math.round((item.utilizado / item.limite) * 100));
}

export function PlanoConsumo() {
  const [plano, setPlano] = useState<PlanoAtual | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");

  useEffect(() => {
    async function carregar() {
      setCarregando(true);
      setErro("");
      try {
        setPlano(await apiRequest<PlanoAtual>("/plano-atual"));
      } catch (error) {
        setErro(
          error instanceof Error
            ? error.message
            : "Não foi possível carregar o plano atual.",
        );
      } finally {
        setCarregando(false);
      }
    }
    void carregar();
  }, []);

  const recursosAtivos = useMemo(
    () => Object.entries(plano?.recursos ?? {}).filter(([, ativo]) => ativo),
    [plano],
  );
  const recursosInativos = useMemo(
    () => Object.entries(plano?.recursos ?? {}).filter(([, ativo]) => !ativo),
    [plano],
  );

  return (
    <div className="page">
      <PageHeader
        eyebrow="Assinatura"
        title="Plano e consumo"
        description="Acompanhe os recursos contratados e os limites utilizados pela empresa."
      />

      {erro && <Alert>{erro}</Alert>}
      {carregando ? (
        <LoadingState label="Carregando plano..." />
      ) : !plano ? (
        <EmptyState
          icon="lock"
          title="Plano não encontrado"
          description="Entre em contato com o responsável pela plataforma."
        />
      ) : (
        <>
          <section className="plan-overview-grid">
            <article className="content-card plan-main-card">
              <div className="plan-name-row">
                <div>
                  <span>Plano atual</span>
                  <h2>{plano.plano_nome ?? "Sem plano definido"}</h2>
                </div>
                {plano.status_empresa && <StatusBadge value={plano.status_empresa} />}
              </div>
              <p>{plano.descricao || "Plano configurado individualmente para esta empresa."}</p>
              <div className="plan-price-row">
                <div>
                  <span>Mensal</span>
                  <strong>{formatCurrency(plano.preco_mensal)}</strong>
                </div>
                <div>
                  <span>Anual</span>
                  <strong>
                    {plano.preco_anual == null
                      ? "Não configurado"
                      : formatCurrency(plano.preco_anual)}
                  </strong>
                </div>
              </div>
              <div className="plan-ia-state">
                <span className={plano.ia_ativa ? "plan-state-dot plan-state-active" : "plan-state-dot"} />
                <div>
                  <strong>
                    {plano.ia_ativa ? "Inteligência artificial ativa" : "Inteligência artificial inativa"}
                  </strong>
                  <small>
                    {plano.ia_adicional_ativo
                      ? "Ativada como adicional do plano."
                      : plano.ia_ativa
                        ? "Incluída no plano atual."
                        : "Pode ser liberada pelo Super Admin conforme o plano."}
                  </small>
                </div>
              </div>
            </article>

            <aside className="content-card plan-dates-card">
              <div>
                <span>Situação da assinatura</span>
                <strong>{plano.status_assinatura ?? "Não informada"}</strong>
              </div>
              <div>
                <span>Início</span>
                <strong>{formatDate(plano.data_inicio)}</strong>
              </div>
              <div>
                <span>Vencimento</span>
                <strong>{formatDate(plano.data_vencimento)}</strong>
              </div>
              <div>
                <span>Fim do teste</span>
                <strong>{formatDate(plano.trial_fim)}</strong>
              </div>
            </aside>
          </section>

          <section className="content-card plan-usage-card">
            <div className="card-heading">
              <div>
                <span>Franquias</span>
                <h2>Consumo atual</h2>
              </div>
            </div>
            <div className="plan-usage-grid">
              {plano.consumo.map((item) => {
                const progresso = percentual(item);
                const alerta = item.limite !== null && progresso >= 80;
                return (
                  <article className={alerta ? "plan-usage-item plan-usage-warning" : "plan-usage-item"} key={item.chave}>
                    <div>
                      <strong>{item.nome}</strong>
                      <span>
                        {item.utilizado} de {item.limite ?? "ilimitado"}
                      </span>
                    </div>
                    {item.limite !== null ? (
                      <div className="plan-progress" aria-label={`${progresso}% utilizado`}>
                        <i style={{ width: `${progresso}%` }} />
                      </div>
                    ) : (
                      <div className="plan-unlimited">Sem limite configurado</div>
                    )}
                    {alerta && <small>Próximo do limite contratado</small>}
                  </article>
                );
              })}
            </div>
          </section>

          <section className="plan-resources-grid">
            <article className="content-card">
              <div className="card-heading">
                <div>
                  <span>Disponível</span>
                  <h2>Recursos ativos</h2>
                </div>
              </div>
              <div className="plan-resource-list">
                {recursosAtivos.map(([recurso]) => (
                  <span className="plan-resource-active" key={recurso}>
                    ✓ {recursoLabels[recurso] ?? recurso}
                  </span>
                ))}
              </div>
            </article>
            <article className="content-card">
              <div className="card-heading">
                <div>
                  <span>Não contratado</span>
                  <h2>Recursos indisponíveis</h2>
                </div>
              </div>
              {recursosInativos.length === 0 ? (
                <div className="compact-empty">Todos os recursos estão disponíveis.</div>
              ) : (
                <div className="plan-resource-list">
                  {recursosInativos.map(([recurso]) => (
                    <span className="plan-resource-inactive" key={recurso}>
                      {recursoLabels[recurso] ?? recurso}
                    </span>
                  ))}
                </div>
              )}
            </article>
          </section>
        </>
      )}
    </div>
  );
}
