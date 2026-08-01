import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { useOutletContext } from "react-router";
import { Icon } from "../components/Icon";
import { Alert, LoadingState, PageHeader } from "../components/UI";
import { apiRequest } from "../services/api";
import type { AppOutletContext, CargoUsuario } from "../types";
import type {
  ChatInternoLeitura,
  ChatInternoMensagem,
} from "../types/internal-chat";

const CHAT_UPDATE_EVENT = "flowdesk:chat-update";

const cargoLabel: Record<CargoUsuario, string> = {
  ADMIN: "Administrador",
  GERENTE: "Gerente",
  FUNCIONARIO: "Funcionário",
};

function iniciais(nome: string): string {
  return nome
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((parte) => parte.charAt(0).toUpperCase())
    .join("");
}

function formatarHorario(valor: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(valor));
}

function formatarData(valor: string): string {
  const data = new Date(valor);
  const hoje = new Date();
  const ontem = new Date();
  ontem.setDate(hoje.getDate() - 1);

  const chave = (item: Date) =>
    `${item.getFullYear()}-${item.getMonth()}-${item.getDate()}`;

  if (chave(data) === chave(hoje)) return "Hoje";
  if (chave(data) === chave(ontem)) return "Ontem";

  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "long",
    year: data.getFullYear() === hoje.getFullYear() ? undefined : "numeric",
  }).format(data);
}

export function ChatInterno() {
  const { usuario } = useOutletContext<AppOutletContext>();
  const [mensagens, setMensagens] = useState<ChatInternoMensagem[]>([]);
  const [conteudo, setConteudo] = useState("");
  const [carregando, setCarregando] = useState(true);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState("");
  const fimRef = useRef<HTMLDivElement | null>(null);
  const primeiraCargaRef = useRef(true);

  const marcarComoLido = useCallback(async () => {
    try {
      await apiRequest<ChatInternoLeitura>("/chat-interno/marcar-lido", {
        method: "POST",
      });
      window.dispatchEvent(new Event(CHAT_UPDATE_EVENT));
    } catch {
      // A leitura será tentada novamente na próxima atualização automática.
    }
  }, []);

  const carregarMensagens = useCallback(
    async (silencioso = false) => {
      if (!silencioso) setCarregando(true);

      try {
        const dados = await apiRequest<ChatInternoMensagem[]>(
          "/chat-interno/mensagens?limit=120",
        );
        setMensagens(dados);
        setErro("");
        await marcarComoLido();
      } catch (error) {
        if (!silencioso) {
          setErro(
            error instanceof Error
              ? error.message
              : "Não foi possível carregar o chat interno.",
          );
        }
      } finally {
        if (!silencioso) setCarregando(false);
      }
    },
    [marcarComoLido],
  );

  useEffect(() => {
    void carregarMensagens();

    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        void carregarMensagens(true);
      }
    }, 5000);

    return () => window.clearInterval(timer);
  }, [carregarMensagens]);

  useEffect(() => {
    if (!mensagens.length) return;
    fimRef.current?.scrollIntoView({
      behavior: primeiraCargaRef.current ? "auto" : "smooth",
      block: "end",
    });
    primeiraCargaRef.current = false;
  }, [mensagens]);

  async function enviarMensagem(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    const texto = conteudo.trim();
    if (!texto || enviando) return;

    setEnviando(true);
    setErro("");

    try {
      const novaMensagem = await apiRequest<ChatInternoMensagem>(
        "/chat-interno/mensagens",
        {
          method: "POST",
          body: JSON.stringify({ conteudo: texto }),
        },
      );

      setMensagens((atuais) => {
        if (atuais.some((item) => item.id === novaMensagem.id)) return atuais;
        return [...atuais, novaMensagem];
      });
      setConteudo("");
      await marcarComoLido();
      window.dispatchEvent(new Event(CHAT_UPDATE_EVENT));
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível enviar a mensagem.",
      );
    } finally {
      setEnviando(false);
    }
  }

  function tratarTecla(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void enviarMensagem();
    }
  }

  let dataAnterior = "";

  return (
    <div className="page internal-chat-page">
      <PageHeader
        eyebrow="Comunicação da equipe"
        title="Chat interno"
        description="Converse com funcionários, gerentes e administradores da sua empresa em uma sala privada."
        actions={
          <div className="internal-chat-status" title="Atualização automática ativa">
            <span />
            Atualização automática
          </div>
        }
      />

      {erro && <Alert>{erro}</Alert>}

      <section className="internal-chat-card" aria-label="Sala geral da empresa">
        <header className="internal-chat-header">
          <div className="internal-chat-room-icon">
            <Icon name="chat" size={22} />
          </div>
          <div>
            <strong>Sala geral</strong>
            <span>Todos os usuários ativos da empresa</span>
          </div>
          <span className={`internal-chat-role role-badge-${usuario.cargo.toLowerCase()}`}>
            {cargoLabel[usuario.cargo]}
          </span>
        </header>

        <div className="internal-chat-messages" aria-live="polite">
          {carregando ? (
            <LoadingState label="Carregando mensagens..." />
          ) : mensagens.length === 0 ? (
            <div className="internal-chat-empty">
              <span>
                <Icon name="chat" size={28} />
              </span>
              <strong>Comece a conversa da equipe</strong>
              <p>Envie a primeira mensagem para a sala geral da empresa.</p>
            </div>
          ) : (
            mensagens.map((mensagem) => {
              const dataAtual = formatarData(mensagem.created_at);
              const mostrarData = dataAtual !== dataAnterior;
              dataAnterior = dataAtual;
              const propria = mensagem.autor.id === usuario.id;

              return (
                <div key={mensagem.id}>
                  {mostrarData && (
                    <div className="internal-chat-date">
                      <span>{dataAtual}</span>
                    </div>
                  )}

                  <article
                    className={`internal-chat-message ${propria ? "internal-chat-message-own" : ""}`}
                  >
                    <div
                      className={`internal-chat-avatar avatar-${mensagem.autor.cargo.toLowerCase()}`}
                      aria-hidden="true"
                    >
                      {mensagem.autor.foto_perfil ? (
                        <img
                          src={mensagem.autor.foto_perfil}
                          alt=""
                          loading="lazy"
                        />
                      ) : (
                        iniciais(mensagem.autor.nome)
                      )}
                    </div>

                    <div className="internal-chat-message-content">
                      <div className="internal-chat-message-meta">
                        <strong>{propria ? "Você" : mensagem.autor.nome}</strong>
                        <span
                          className={`internal-chat-role role-badge-${mensagem.autor.cargo.toLowerCase()}`}
                        >
                          {cargoLabel[mensagem.autor.cargo]}
                        </span>
                        <time dateTime={mensagem.created_at}>
                          {formatarHorario(mensagem.created_at)}
                        </time>
                      </div>
                      <p>{mensagem.conteudo}</p>
                    </div>
                  </article>
                </div>
              );
            })
          )}
          <div ref={fimRef} />
        </div>

        <form className="internal-chat-composer" onSubmit={enviarMensagem}>
          <label className="sr-only" htmlFor="mensagem-chat-interno">
            Mensagem para a equipe
          </label>
          <textarea
            id="mensagem-chat-interno"
            value={conteudo}
            onChange={(event) => setConteudo(event.target.value)}
            onKeyDown={tratarTecla}
            placeholder="Escreva uma mensagem para a equipe..."
            maxLength={2000}
            rows={1}
            disabled={enviando}
          />
          <div className="internal-chat-composer-footer">
            <span>Enter envia · Shift + Enter quebra a linha</span>
            <span>{conteudo.length}/2000</span>
          </div>
          <button
            className="button button-primary internal-chat-send"
            type="submit"
            disabled={!conteudo.trim() || enviando}
          >
            <Icon name="send" size={18} />
            {enviando ? "Enviando..." : "Enviar"}
          </button>
        </form>
      </section>
    </div>
  );
}
