import { useMemo, useState } from "react";
import { Icon } from "../components/Icon";
import { PageHeader } from "../components/UI";
import { apiRequest } from "../services/api";
import { showAppToast } from "../services/feedback";
import "../whatsapp-simulator.css";

interface SimulatorLinkResponse {
  path: string;
  expires_at: string;
  validade_dias: number;
}

export function ConfiguracaoSimuladorIA() {
  const [validadeDias, setValidadeDias] = useState<1 | 7 | 30>(7);
  const [gerando, setGerando] = useState(false);
  const [linkGerado, setLinkGerado] = useState<SimulatorLinkResponse | null>(null);

  const fullLink = useMemo(() => {
    if (!linkGerado) return "";
    return `${window.location.origin}${linkGerado.path}`;
  }, [linkGerado]);

  async function gerarLink() {
    setGerando(true);
    try {
      const response = await apiRequest<SimulatorLinkResponse>("/simulador-ia/link", {
        method: "POST",
        body: JSON.stringify({ validade_dias: validadeDias }),
      });
      setLinkGerado(response);
      showAppToast("Link secreto do simulador gerado com sucesso.");
    } catch (error) {
      showAppToast(
        error instanceof Error ? error.message : "Não foi possível gerar o link do simulador.",
        { type: "error" },
      );
    } finally {
      setGerando(false);
    }
  }

  async function copiarLink() {
    if (!fullLink) return;
    try {
      await navigator.clipboard.writeText(fullLink);
      showAppToast("Link copiado para a área de transferência.");
    } catch {
      showAppToast("Não foi possível copiar automaticamente. Selecione o link e copie manualmente.", {
        type: "warning",
      });
    }
  }

  return (
    <div className="page simulator-settings-page">
      <PageHeader
        eyebrow="Laboratório de IA"
        title="Simulador de atendimento"
        description="Teste a experiência da IA como se o cliente estivesse conversando pelo WhatsApp, sem precisar conectar um número real."
      />

      <section className="simulator-settings-grid">
        <article className="card simulator-settings-card">
          <div className="simulator-settings-card-heading">
            <span className="simulator-settings-icon">
              <Icon name="bot" size={22} />
            </span>
            <div>
              <h2>Link privado de teste</h2>
              <p>
                O endereço contém uma chave temporária vinculada somente a esta empresa.
                Quem não tiver o link válido não consegue abrir o simulador.
              </p>
            </div>
          </div>

          <label className="simulator-validity-field">
            Validade do link
            <select
              value={validadeDias}
              onChange={(event) => setValidadeDias(Number(event.target.value) as 1 | 7 | 30)}
            >
              <option value={1}>1 dia</option>
              <option value={7}>7 dias</option>
              <option value={30}>30 dias</option>
            </select>
          </label>

          <button
            className="button button-primary"
            type="button"
            onClick={() => void gerarLink()}
            disabled={gerando}
          >
            <Icon name="lock" size={17} />
            {gerando ? "Gerando link..." : linkGerado ? "Gerar novo link" : "Gerar link de teste"}
          </button>

          {linkGerado && (
            <div className="simulator-generated-link">
              <label>
                Link secreto
                <input value={fullLink} readOnly onFocus={(event) => event.currentTarget.select()} />
              </label>
              <div className="simulator-generated-actions">
                <button className="button button-secondary" type="button" onClick={() => void copiarLink()}>
                  <Icon name="check" size={16} />
                  Copiar
                </button>
                <button
                  className="button button-secondary"
                  type="button"
                  onClick={() => window.open(fullLink, "_blank", "noopener,noreferrer")}
                >
                  <Icon name="eye" size={16} />
                  Abrir simulador
                </button>
              </div>
              <small>
                Válido até {new Date(linkGerado.expires_at).toLocaleString("pt-BR")}.
                Um link novo não cancela links anteriores; eles expiram automaticamente.
              </small>
            </div>
          )}
        </article>

        <article className="card simulator-settings-card simulator-settings-info">
          <h2>O que este laboratório testa</h2>
          <div className="simulator-check-list">
            <span><Icon name="check" size={16} /> contexto real da empresa e dos serviços</span>
            <span><Icon name="check" size={16} /> prompt e nome do assistente configurados no FlowDeskIA</span>
            <span><Icon name="check" size={16} /> conversa contínua com até 20 mensagens de contexto</span>
            <span><Icon name="check" size={16} /> comportamento de atendimento curto, no estilo WhatsApp</span>
            <span><Icon name="check" size={16} /> testes de preço, agendamento, humano e tentativa de manipular a IA</span>
          </div>

          <div className="simulator-safety-note">
            <strong>Sandbox seguro</strong>
            <p>
              O cliente e o veículo usados no simulador são fictícios. O teste não cria clientes,
              não agenda horários e não altera dados reais. Ele consulta o contexto real da empresa
              para avaliar exatamente a qualidade da resposta da IA antes da integração com WhatsApp.
            </p>
          </div>
        </article>
      </section>
    </div>
  );
}
