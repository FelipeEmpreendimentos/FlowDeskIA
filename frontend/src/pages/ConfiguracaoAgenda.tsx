import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useOutletContext } from "react-router";
import { Icon } from "../components/Icon";
import { Alert, LoadingState, PageHeader } from "../components/UI";
import { apiRequest } from "../services/api";
import { showAppToast } from "../services/feedback";
import type { AppOutletContext, Servico, Usuario } from "../types";

interface ConfiguracaoAgendaData {
  empresa_id: number;
  intervalo_minutos: number;
}

interface QualificacaoServico {
  servico_id: number;
  funcionario_ids: number[];
}

export function ConfiguracaoAgenda() {
  const { usuario } = useOutletContext<AppOutletContext>();
  const [intervalo, setIntervalo] = useState("30");
  const [servicos, setServicos] = useState<Servico[]>([]);
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [qualificacoes, setQualificacoes] = useState<Record<number, number[]>>({});
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");

  const podeEditar = usuario.cargo === "ADMIN";

  const servicosAtivos = useMemo(
    () => servicos.filter((item) => item.ativo).sort((a, b) => a.nome.localeCompare(b.nome)),
    [servicos],
  );
  const usuariosAtivos = useMemo(
    () => usuarios.filter((item) => item.ativo).sort((a, b) => a.nome.localeCompare(b.nome)),
    [usuarios],
  );

  useEffect(() => {
    async function carregar() {
      setCarregando(true);
      setErro("");
      try {
        const [configuracao, dadosServicos, dadosUsuarios, dadosQualificacoes] =
          await Promise.all([
            apiRequest<ConfiguracaoAgendaData>("/configuracoes-agenda"),
            apiRequest<Servico[]>("/servicos?ativo=true&limit=100"),
            apiRequest<Usuario[]>("/usuarios?ativo=true&limit=100"),
            apiRequest<QualificacaoServico[]>("/servicos-qualificacoes"),
          ]);

        setIntervalo(String(configuracao.intervalo_minutos));
        setServicos(dadosServicos);
        setUsuarios(dadosUsuarios);
        setQualificacoes(
          Object.fromEntries(
            dadosQualificacoes.map((item) => [item.servico_id, item.funcionario_ids]),
          ),
        );
      } catch (error) {
        setErro(
          error instanceof Error
            ? error.message
            : "Não foi possível carregar as configurações da agenda.",
        );
      } finally {
        setCarregando(false);
      }
    }

    void carregar();
  }, []);

  function alternarFuncionario(servicoId: number, funcionarioId: number) {
    if (!podeEditar || salvando) return;
    setQualificacoes((atuais) => {
      const selecionados = atuais[servicoId] ?? [];
      return {
        ...atuais,
        [servicoId]: selecionados.includes(funcionarioId)
          ? selecionados.filter((id) => id !== funcionarioId)
          : [...selecionados, funcionarioId],
      };
    });
  }

  async function salvar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!podeEditar) return;

    const semEquipe = servicosAtivos.find(
      (servico) => (qualificacoes[servico.id] ?? []).length === 0,
    );
    if (semEquipe) {
      setErro(`Selecione pelo menos um funcionário para ${semEquipe.nome}.`);
      return;
    }

    setSalvando(true);
    setErro("");
    try {
      const [configuracao] = await Promise.all([
        apiRequest<ConfiguracaoAgendaData>("/configuracoes-agenda", {
          method: "PATCH",
          body: JSON.stringify({ intervalo_minutos: Number(intervalo) }),
        }),
        ...servicosAtivos.map((servico) =>
          apiRequest<QualificacaoServico>(`/servicos/${servico.id}/funcionarios`, {
            method: "PUT",
            body: JSON.stringify({
              funcionario_ids: qualificacoes[servico.id] ?? [],
            }),
          }),
        ),
      ]);
      setIntervalo(String(configuracao.intervalo_minutos));
      showAppToast("Configurações da agenda e equipes dos serviços salvas com sucesso.");
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível salvar as configurações da agenda.",
      );
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="page agenda-settings-page">
      <PageHeader
        eyebrow="Configuração operacional"
        title="Configurações da agenda"
        description="Defina os intervalos e quais funcionários estão habilitados para cada serviço."
        actions={
          <Link className="button button-secondary" to="/configuracoes">
            <Icon name="arrow-left" size={17} />
            Voltar
          </Link>
        }
      />

      {erro && <Alert>{erro}</Alert>}

      {carregando ? (
        <LoadingState label="Carregando configurações da agenda..." />
      ) : (
        <form className="agenda-settings-stack" onSubmit={salvar}>
          <section className="content-card agenda-settings-card">
            <div className="card-heading">
              <div>
                <span>Disponibilidade</span>
                <h2>Intervalo entre os horários</h2>
              </div>
              <Icon name="clock" size={24} />
            </div>

            {!podeEditar && (
              <Alert type="info">
                Somente administradores podem alterar estas configurações.
              </Alert>
            )}

            <label className="field agenda-interval-field">
              Oferecer horários a cada
              <select
                value={intervalo}
                onChange={(event) => setIntervalo(event.target.value)}
                disabled={!podeEditar || salvando}
              >
                <option value="15">15 minutos</option>
                <option value="30">30 minutos</option>
                <option value="60">60 minutos</option>
              </select>
              <small className="field-help">
                A duração do serviço, a jornada, os intervalos e os bloqueios do
                funcionário continuam sendo respeitados automaticamente.
              </small>
            </label>
          </section>

          <section className="content-card agenda-service-team-card">
            <div className="card-heading">
              <div>
                <span>Distribuição automática</span>
                <h2>Quem realiza cada serviço</h2>
              </div>
              <Icon name="team" size={24} />
            </div>

            <p className="agenda-service-team-intro">
              O “Qualquer funcionário” considera somente as pessoas marcadas para
              o serviço. Entre elas, o sistema prioriza menor carga no dia, maior
              espaço até o próximo atendimento e depois o rodízio.
            </p>

            {servicosAtivos.length === 0 ? (
              <div className="compact-empty">Nenhum serviço ativo cadastrado.</div>
            ) : usuariosAtivos.length === 0 ? (
              <Alert type="info">
                Cadastre pelo menos um usuário ativo antes de configurar as equipes.
              </Alert>
            ) : (
              <div className="agenda-service-team-list">
                {servicosAtivos.map((servico) => {
                  const selecionados = qualificacoes[servico.id] ?? [];
                  return (
                    <article className="agenda-service-team-row" key={servico.id}>
                      <div className="agenda-service-team-service">
                        <span
                          className="agenda-service-team-color"
                          style={{ background: servico.cor_agenda ?? "#3157D5" }}
                        />
                        <div>
                          <strong>{servico.nome}</strong>
                          <small>
                            {selecionados.length} funcionário
                            {selecionados.length === 1 ? "" : "s"} habilitado
                            {selecionados.length === 1 ? "" : "s"}
                          </small>
                        </div>
                      </div>

                      <div className="agenda-service-team-users">
                        {usuariosAtivos.map((funcionario) => {
                          const marcado = selecionados.includes(funcionario.id);
                          return (
                            <label
                              className={`agenda-service-team-user ${marcado ? "agenda-service-team-user-active" : ""}`}
                              key={funcionario.id}
                            >
                              <input
                                type="checkbox"
                                checked={marcado}
                                onChange={() =>
                                  alternarFuncionario(servico.id, funcionario.id)
                                }
                                disabled={!podeEditar || salvando}
                              />
                              <span>{funcionario.nome}</span>
                            </label>
                          );
                        })}
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </section>

          {podeEditar && (
            <div className="form-footer agenda-settings-save">
              <button
                className="button button-primary"
                type="submit"
                disabled={salvando || usuariosAtivos.length === 0}
              >
                {salvando ? "Salvando..." : "Salvar configurações"}
              </button>
            </div>
          )}
        </form>
      )}
    </div>
  );
}
