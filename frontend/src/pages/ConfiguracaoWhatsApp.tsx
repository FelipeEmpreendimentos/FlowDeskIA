import { useEffect, useRef, useState } from "react";
import { useOutletContext } from "react-router";
import { Icon } from "../components/Icon";
import { Modal } from "../components/Modal";
import { Alert, LoadingState, PageHeader } from "../components/UI";
import { apiRequest } from "../services/api";
import { showAppToast } from "../services/feedback";
import type { AppOutletContext } from "../types";
import type { CurrentAccess } from "../types/accessControl";

type ConnectionMode = "COEXISTENCE" | "CLOUD_API";

interface WhatsAppIntegration {
  connected: boolean;
  phone_number_id: string | null;
  waba_id: string | null;
  business_id: string | null;
  display_phone_number: string | null;
  verified_name: string | null;
  quality_rating: string | null;
  connection_mode: ConnectionMode | null;
  updated_at: string | null;
}

interface MetaSessionInfo {
  phone_number_id?: string;
  waba_id?: string;
  business_id?: string;
}

interface MetaLoginResponse {
  authResponse?: { code?: string };
  status?: string;
}

interface MetaSdk {
  init(options: {
    appId: string;
    cookie: boolean;
    xfbml: boolean;
    version: string;
  }): void;
  login(
    callback: (response: MetaLoginResponse) => void,
    options: Record<string, unknown>,
  ): void;
}

declare global {
  interface Window {
    FB?: MetaSdk;
    fbAsyncInit?: () => void;
  }
}

const META_APP_ID = import.meta.env.VITE_META_APP_ID || "1940689196889345";
const META_CONFIG_ID = import.meta.env.VITE_META_WHATSAPP_CONFIG_ID || "";
const META_GRAPH_VERSION = "v25.0";

let sdkPromise: Promise<void> | null = null;

function loadMetaSdk(): Promise<void> {
  if (window.FB) return Promise.resolve();
  if (sdkPromise) return sdkPromise;

  sdkPromise = new Promise((resolve, reject) => {
    window.fbAsyncInit = () => {
      if (!window.FB) {
        reject(new Error("Não foi possível carregar a conexão da Meta."));
        return;
      }
      window.FB.init({
        appId: META_APP_ID,
        cookie: true,
        xfbml: false,
        version: META_GRAPH_VERSION,
      });
      resolve();
    };

    const existing = document.getElementById("meta-jssdk");
    if (existing) return;

    const script = document.createElement("script");
    script.id = "meta-jssdk";
    script.async = true;
    script.defer = true;
    script.crossOrigin = "anonymous";
    script.src = "https://connect.facebook.net/pt_BR/sdk.js";
    script.onerror = () => reject(new Error("Não foi possível carregar a conexão da Meta."));
    document.body.appendChild(script);
  });

  return sdkPromise;
}

function connectionModeLabel(mode: ConnectionMode | null): string {
  return mode === "COEXISTENCE" ? "WhatsApp Business + FlowDeskIA" : "Cloud API da Meta";
}

export function ConfiguracaoWhatsApp() {
  const { modulos } = useOutletContext<AppOutletContext>();
  const [integration, setIntegration] = useState<WhatsAppIntegration | null>(null);
  const [canManage, setCanManage] = useState(false);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [modeModalOpen, setModeModalOpen] = useState(false);
  const [error, setError] = useState("");
  const sessionRef = useRef<MetaSessionInfo | null>(null);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [status, access] = await Promise.all([
        apiRequest<WhatsAppIntegration>("/whatsapp/integracao"),
        apiRequest<CurrentAccess>("/acessos/me"),
      ]);
      setIntegration(status);
      setCanManage(Boolean(access.management.WHATSAPP));
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Não foi possível carregar a integração do WhatsApp.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    function receiveEmbeddedSignup(event: MessageEvent) {
      if (![
        "https://www.facebook.com",
        "https://web.facebook.com",
      ].includes(event.origin)) {
        return;
      }

      let data: unknown = event.data;
      if (typeof data === "string") {
        try {
          data = JSON.parse(data);
        } catch {
          return;
        }
      }
      if (!data || typeof data !== "object") return;

      const message = data as {
        type?: string;
        event?: string;
        data?: MetaSessionInfo;
      };
      if (message.type !== "WA_EMBEDDED_SIGNUP") return;
      if (message.event === "FINISH" && message.data) {
        sessionRef.current = message.data;
      }
    }

    window.addEventListener("message", receiveEmbeddedSignup);
    return () => window.removeEventListener("message", receiveEmbeddedSignup);
  }, []);

  async function waitForSession(): Promise<MetaSessionInfo | null> {
    for (let attempt = 0; attempt < 50; attempt += 1) {
      if (sessionRef.current?.phone_number_id && sessionRef.current?.waba_id) {
        return sessionRef.current;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 100));
    }
    return null;
  }

  async function connect(mode: ConnectionMode) {
    setModeModalOpen(false);
    setError("");

    if (!META_CONFIG_ID) {
      showAppToast(
        "A tela do FlowDeskIA está pronta, mas falta informar a Configuração de Cadastro Incorporado criada na Meta.",
        { type: "warning" },
      );
      return;
    }

    setProcessing(true);
    sessionRef.current = null;

    try {
      await loadMetaSdk();
      if (!window.FB) throw new Error("A conexão da Meta não foi carregada.");

      window.FB.login(
        async (response) => {
          const code = response.authResponse?.code;
          if (!code) {
            setProcessing(false);
            if (response.status) {
              setError("A conexão com a Meta não foi concluída.");
            }
            return;
          }

          const session = await waitForSession();
          if (!session?.phone_number_id || !session.waba_id) {
            setProcessing(false);
            setError("A Meta não retornou os dados do número conectado. Tente novamente.");
            return;
          }

          try {
            const connected = await apiRequest<WhatsAppIntegration>("/whatsapp/conectar", {
              method: "POST",
              body: JSON.stringify({
                code,
                waba_id: session.waba_id,
                phone_number_id: session.phone_number_id,
                business_id: session.business_id ?? null,
                connection_mode: mode,
              }),
            });
            setIntegration(connected);
            showAppToast("WhatsApp conectado ao FlowDeskIA com sucesso.");
          } catch (connectError) {
            setError(
              connectError instanceof Error
                ? connectError.message
                : "Não foi possível concluir a conexão do WhatsApp.",
            );
          } finally {
            setProcessing(false);
          }
        },
        {
          config_id: META_CONFIG_ID,
          response_type: "code",
          override_default_response_type: true,
          extras:
            mode === "COEXISTENCE"
              ? {
                  setup: {},
                  featureType: "whatsapp_business_app_onboarding",
                  sessionInfoVersion: "3",
                }
              : {
                  setup: {},
                  sessionInfoVersion: "3",
                },
        },
      );
    } catch (connectError) {
      setProcessing(false);
      setError(
        connectError instanceof Error
          ? connectError.message
          : "Não foi possível abrir a conexão da Meta.",
      );
    }
  }

  async function testConnection() {
    setProcessing(true);
    setError("");
    try {
      const result = await apiRequest<{
        message: string;
        display_phone_number: string | null;
        verified_name: string | null;
      }>("/whatsapp/testar", { method: "POST" });
      showAppToast(result.message);
      await load();
    } catch (testError) {
      setError(
        testError instanceof Error
          ? testError.message
          : "Não foi possível validar a conexão.",
      );
    } finally {
      setProcessing(false);
    }
  }

  async function disconnect() {
    if (!window.confirm("Desconectar este WhatsApp do FlowDeskIA?")) return;
    setProcessing(true);
    setError("");
    try {
      const disconnected = await apiRequest<WhatsAppIntegration>("/whatsapp/desconectar", {
        method: "POST",
      });
      setIntegration(disconnected);
      showAppToast("WhatsApp desconectado do FlowDeskIA.");
    } catch (disconnectError) {
      setError(
        disconnectError instanceof Error
          ? disconnectError.message
          : "Não foi possível desconectar o WhatsApp.",
      );
    } finally {
      setProcessing(false);
    }
  }

  if (!modulos.WHATSAPP) {
    return (
      <div className="page whatsapp-settings-page">
        <PageHeader
          eyebrow="Integrações"
          title="WhatsApp"
          description="Esta integração não está liberada para o seu usuário."
        />
        <Alert>Esta integração não está liberada para o seu usuário.</Alert>
      </div>
    );
  }

  return (
    <div className="page whatsapp-settings-page">
      <PageHeader
        eyebrow="Atendimento conectado"
        title="WhatsApp e integrações"
        description="Conecte o número da empresa à API oficial da Meta e use as conversas, a IA e a agenda do FlowDeskIA no mesmo atendimento."
      />

      {error && <Alert>{error}</Alert>}

      {loading || !integration ? (
        <section className="content-card">
          <LoadingState label="Carregando WhatsApp..." />
        </section>
      ) : integration.connected ? (
        <section className="content-card whatsapp-connection-card whatsapp-connected-card">
          <div className="whatsapp-connection-heading">
            <span className="whatsapp-brand-icon">
              <Icon name="chat" size={24} />
            </span>
            <div>
              <span className="whatsapp-status whatsapp-status-connected">
                <i /> Conectado
              </span>
              <h2>{integration.verified_name || "WhatsApp da empresa"}</h2>
              <p>{integration.display_phone_number || "Número conectado pela Meta"}</p>
            </div>
          </div>

          <div className="whatsapp-details-grid">
            <div>
              <span>Modo de conexão</span>
              <strong>{connectionModeLabel(integration.connection_mode)}</strong>
            </div>
            <div>
              <span>Qualidade</span>
              <strong>{integration.quality_rating || "Disponível após validação"}</strong>
            </div>
          </div>

          {canManage && (
            <div className="whatsapp-actions">
              <button
                className="button button-secondary"
                type="button"
                onClick={() => void testConnection()}
                disabled={processing}
              >
                Testar conexão
              </button>
              <button
                className="button button-danger"
                type="button"
                onClick={() => void disconnect()}
                disabled={processing}
              >
                Desconectar
              </button>
            </div>
          )}
        </section>
      ) : (
        <section className="content-card whatsapp-connection-card">
          <div className="whatsapp-empty-state">
            <span className="whatsapp-brand-icon">
              <Icon name="chat" size={26} />
            </span>
            <div>
              <span className="whatsapp-status"><i /> Não conectado</span>
              <h2>Conecte o WhatsApp da empresa</h2>
              <p>
                O processo é feito pela própria Meta. Para quem já usa o WhatsApp Business no celular, o FlowDeskIA prioriza a coexistência para manter o aplicativo funcionando.
              </p>
            </div>
          </div>

          <div className="whatsapp-benefits">
            <span><Icon name="check" size={15} /> Atendimento entrando direto em Conversas</span>
            <span><Icon name="check" size={15} /> IA e botões usando o fluxo atual do FlowDeskIA</span>
            <span><Icon name="check" size={15} /> Controle por permissões de usuário</span>
          </div>

          {canManage ? (
            <button
              className="button button-primary whatsapp-connect-button"
              type="button"
              onClick={() => setModeModalOpen(true)}
              disabled={processing}
            >
              <Icon name="chat" size={18} />
              {processing ? "Conectando..." : "Conectar WhatsApp"}
            </button>
          ) : (
            <p className="whatsapp-permission-note">
              Você pode consultar esta integração, mas não possui permissão para conectá-la ou alterá-la.
            </p>
          )}
        </section>
      )}

      <Modal
        open={modeModalOpen}
        onClose={() => setModeModalOpen(false)}
        title="Como este número é usado?"
        subtitle="Escolha o caminho e a Meta continua a conexão."
        size="medium"
      >
        <div className="whatsapp-mode-options">
          <button type="button" onClick={() => void connect("COEXISTENCE")}>
            <span className="whatsapp-mode-icon"><Icon name="chat" size={21} /></span>
            <div>
              <strong>Já uso WhatsApp Business no celular</strong>
              <p>Recomendado. Mantém o número no aplicativo e conecta o FlowDeskIA pela API oficial.</p>
              <small>A Meta poderá mostrar o QR Code de coexistência.</small>
            </div>
            <span aria-hidden="true">→</span>
          </button>
          <button type="button" onClick={() => void connect("CLOUD_API")}>
            <span className="whatsapp-mode-icon"><Icon name="settings" size={21} /></span>
            <div>
              <strong>Número para Cloud API</strong>
              <p>Para um número dedicado à plataforma da Meta, com verificação feita no fluxo oficial.</p>
              <small>Este caminho não usa o QR Code do WhatsApp Business.</small>
            </div>
            <span aria-hidden="true">→</span>
          </button>
        </div>
      </Modal>
    </div>
  );
}
