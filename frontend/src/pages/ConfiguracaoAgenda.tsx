import { useEffect, useState, type FormEvent } from "react";
import { Link, useOutletContext } from "react-router";
import { Icon } from "../components/Icon";
import { Alert, LoadingState, PageHeader } from "../components/UI";
import { apiRequest } from "../services/api";
import { showAppToast } from "../services/feedback";
import type { AppOutletContext } from "../types";

interface ConfiguracaoAgendaData {
  empresa_id: number;
  intervalo_minutos: number;
}

export function ConfiguracaoAgenda() {
  const { usuario } = useOutletContext<AppOutletContext>();
  const [intervalo, setIntervalo] = useState("30");
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");

  const podeEditar = usuario.cargo === "ADMIN";

  useEffect(() => {
    async function carregar() {
      setCarregando(true);
      setErro("");
      try {
        const data = await apiRequest<ConfiguracaoAgendaData>(
          "/configuracoes-agenda",
        );
        setIntervalo(String(data.intervalo_minutos));
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

  async function salvar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!podeEditar) return;

    setSalvando(true);
    setErro("");
    try {
      const data = await apiRequest<ConfiguracaoAgendaData>(
        "/configuracoes-agenda",
        {
          method: "PATCH",
          body: JSON.stringify({ intervalo_minutos: Number(intervalo) }),
        },
      );
      setIntervalo(String(data.intervalo_minutos));
      showAppToast("Intervalo dos horários atualizado com sucesso.");
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
        description="Defina de quanto em quanto tempo os horários disponíveis serão oferecidos."
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
              Somente administradores podem alterar esta configuração.
            </Alert>
          )}

          <form onSubmit={salvar}>
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

            {podeEditar && (
              <div className="form-footer">
                <button
                  className="button button-primary"
                  type="submit"
                  disabled={salvando}
                >
                  {salvando ? "Salvando..." : "Salvar configuração"}
                </button>
              </div>
            )}
          </form>
        </section>
      )}
    </div>
  );
}
