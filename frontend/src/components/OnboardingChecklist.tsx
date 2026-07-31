import { useEffect, useState } from "react";
import { Link } from "react-router";
import { apiRequest } from "../services/api";
import { Icon } from "./Icon";

interface EtapaOnboarding {
  chave: string;
  titulo: string;
  descricao: string;
  concluida: boolean;
  link: string;
}

interface OnboardingData {
  oculto: boolean;
  concluido: boolean;
  percentual: number;
  concluidas: number;
  total: number;
  etapas: EtapaOnboarding[];
}

export function OnboardingChecklist({ ativo }: { ativo: boolean }) {
  const [dados, setDados] = useState<OnboardingData | null>(null);
  const [carregando, setCarregando] = useState(ativo);

  async function carregar() {
    if (!ativo) return;
    setCarregando(true);
    try {
      setDados(await apiRequest<OnboardingData>("/onboarding"));
    } catch {
      setDados(null);
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    void carregar();
  }, [ativo]);

  async function ocultar() {
    if (!dados) return;
    try {
      setDados(
        await apiRequest<OnboardingData>("/onboarding/visibilidade", {
          method: "PATCH",
          body: JSON.stringify({ oculto: true }),
        }),
      );
    } catch {
      // O checklist é complementar e não bloqueia o restante do painel.
    }
  }

  if (!ativo || carregando || !dados || dados.oculto) return null;

  return (
    <section className="content-card onboarding-card">
      <div className="onboarding-heading">
        <div>
          <span>Primeiros passos</span>
          <h2>
            {dados.concluido
              ? "Configuração inicial concluída"
              : "Prepare sua empresa para começar"}
          </h2>
          <p>
            {dados.concluidas} de {dados.total} etapas concluídas
          </p>
        </div>
        <button
          className="icon-button"
          type="button"
          onClick={() => void ocultar()}
          aria-label="Ocultar checklist"
          title="Ocultar checklist"
        >
          <Icon name="close" size={17} />
        </button>
      </div>

      <div className="onboarding-progress" aria-label={`${dados.percentual}% concluído`}>
        <i style={{ width: `${dados.percentual}%` }} />
      </div>

      <div className="onboarding-steps">
        {dados.etapas.map((etapa) => (
          <Link
            className={etapa.concluida ? "onboarding-step onboarding-step-done" : "onboarding-step"}
            key={etapa.chave}
            to={etapa.link}
          >
            <span className="onboarding-step-icon">
              <Icon name={etapa.concluida ? "check" : "arrow-left"} size={16} />
            </span>
            <div>
              <strong>{etapa.titulo}</strong>
              <small>{etapa.descricao}</small>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
