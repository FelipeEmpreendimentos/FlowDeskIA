import { useEffect, useState } from "react";
import { Icon } from "../components/Icon";
import { Alert, EmptyState, LoadingState, PageHeader } from "../components/UI";
import { apiRequest, buildQuery } from "../services/api";
import type { Usuario } from "../types";
import { formatDateTime, todayISO } from "../utils/format";

interface Atividade {
  id: number;
  usuario_id: number | null;
  usuario_nome: string | null;
  usuario_cargo: string | null;
  acao: string;
  entidade: string | null;
  entidade_id: number | null;
  descricao: string;
  detalhes: Record<string, unknown> | null;
  created_at: string;
}

function primeiroDiaDoMes() {
  return `${todayISO().slice(0, 7)}-01`;
}

export function Atividades() {
  const [atividades, setAtividades] = useState<Atividade[]>([]);
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [dataInicio, setDataInicio] = useState(primeiroDiaDoMes());
  const [dataFim, setDataFim] = useState(todayISO());
  const [usuarioId, setUsuarioId] = useState("");
  const [entidade, setEntidade] = useState("");
  const [busca, setBusca] = useState("");
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [detalhesAbertos, setDetalhesAbertos] = useState<Set<number>>(new Set());

  async function carregar() {
    setCarregando(true);
    setErro("");
    try {
      const query = buildQuery({
        data_inicio: dataInicio,
        data_fim: dataFim,
        usuario_id: usuarioId,
        entidade,
        busca,
        limit: 300,
      });
      const [dadosAtividades, dadosUsuarios] = await Promise.all([
        apiRequest<Atividade[]>(`/atividades${query}`),
        usuarios.length
          ? Promise.resolve(usuarios)
          : apiRequest<Usuario[]>("/usuarios?limit=100"),
      ]);
      setAtividades(dadosAtividades);
      setUsuarios(dadosUsuarios);
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível carregar as atividades.",
      );
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => void carregar(), 250);
    return () => window.clearTimeout(timer);
  }, [dataInicio, dataFim, usuarioId, entidade, busca]);

  function alternarDetalhes(id: number) {
    setDetalhesAbertos((atuais) => {
      const proximo = new Set(atuais);
      if (proximo.has(id)) proximo.delete(id);
      else proximo.add(id);
      return proximo;
    });
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Auditoria"
        title="Histórico de atividades"
        description="Veja quem realizou cada alteração importante dentro da empresa."
      />

      {erro && <Alert>{erro}</Alert>}

      <section className="content-card activity-filter-card">
        <div className="activity-filters">
          <label className="search-field activity-search">
            <Icon name="search" size={18} />
            <input
              value={busca}
              onChange={(event) => setBusca(event.target.value)}
              placeholder="Buscar ação, usuário ou entidade"
            />
          </label>
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
            Usuário
            <select value={usuarioId} onChange={(event) => setUsuarioId(event.target.value)}>
              <option value="">Todos</option>
              {usuarios.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.nome}
                </option>
              ))}
            </select>
          </label>
          <label className="field compact-field">
            Área
            <select value={entidade} onChange={(event) => setEntidade(event.target.value)}>
              <option value="">Todas</option>
              <option value="agendamentos">Agendamentos</option>
              <option value="fechamentos_financeiros">Financeiro</option>
              <option value="pagamentos_atendimento">Pagamentos</option>
              <option value="clientes">Clientes</option>
              <option value="veiculos">Veículos</option>
              <option value="servicos">Serviços</option>
              <option value="usuarios">Equipe</option>
              <option value="conversas">Conversas</option>
            </select>
          </label>
        </div>
      </section>

      <section className="content-card">
        {carregando ? (
          <LoadingState label="Carregando atividades..." />
        ) : atividades.length === 0 ? (
          <EmptyState
            icon="clock"
            title="Nenhuma atividade encontrada"
            description="Altere os filtros ou realize uma operação no sistema."
          />
        ) : (
          <div className="activity-list">
            {atividades.map((item) => (
              <article className="activity-item" key={item.id}>
                <span className="activity-icon">
                  <Icon name={item.entidade?.includes("pagamento") || item.entidade?.includes("financeiro") ? "finance" : "clock"} size={18} />
                </span>
                <div className="activity-copy">
                  <strong>{item.descricao}</strong>
                  <span>
                    {item.usuario_cargo || "SISTEMA"} · {formatDateTime(item.created_at)}
                  </span>
                  {item.detalhes && detalhesAbertos.has(item.id) && (
                    <pre>{JSON.stringify(item.detalhes, null, 2)}</pre>
                  )}
                </div>
                {item.detalhes && (
                  <button
                    className="button button-small button-secondary"
                    type="button"
                    onClick={() => alternarDetalhes(item.id)}
                  >
                    {detalhesAbertos.has(item.id) ? "Ocultar" : "Detalhes"}
                  </button>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
