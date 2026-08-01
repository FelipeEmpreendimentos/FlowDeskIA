import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { useOutletContext } from "react-router";
import { Icon } from "../components/Icon";
import { Modal } from "../components/Modal";
import { Alert, LoadingState } from "../components/UI";
import { apiRequest } from "../services/api";
import type { AppOutletContext, CargoUsuario } from "../types";
import type {
  ChatInternoCanal,
  ChatInternoLeitura,
  ChatInternoMensagem,
  ChatInternoUsuario,
} from "../types/internal-chat";

const CHAT_UPDATE_EVENT = "flowdesk:chat-update";

type AbaChat = "CONVERSAS" | "GRUPOS";

interface ConversaUsuario {
  pessoa: ChatInternoUsuario;
  canal: ChatInternoCanal | null;
}

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

function resumoMensagem(canal: ChatInternoCanal | null): string {
  if (!canal?.ultima_mensagem) {
    return canal?.tipo === "GRUPO" || canal?.tipo === "GERAL"
      ? "Nenhuma mensagem ainda"
      : "Conversa direta";
  }

  const texto = canal.ultima_mensagem.conteudo.replace(/\s+/g, " ").trim();
  return `${canal.ultima_mensagem.autor.nome}: ${texto}`;
}

function dataOrdenacao(canal: ChatInternoCanal | null): number {
  if (!canal) return 0;
  return new Date(canal.ultima_mensagem?.created_at ?? canal.created_at).getTime();
}

function ordenarGrupos(canais: ChatInternoCanal[]): ChatInternoCanal[] {
  return [...canais].sort((a, b) => {
    if (a.tipo === "GERAL" && b.tipo !== "GERAL") return -1;
    if (b.tipo === "GERAL" && a.tipo !== "GERAL") return 1;
    return dataOrdenacao(b) - dataOrdenacao(a);
  });
}

export function ChatInterno() {
  const { usuario } = useOutletContext<AppOutletContext>();
  const [aba, setAba] = useState<AbaChat>("CONVERSAS");
  const [usuarios, setUsuarios] = useState<ChatInternoUsuario[]>([]);
  const [canais, setCanais] = useState<ChatInternoCanal[]>([]);
  const [canalId, setCanalId] = useState<number | null>(null);
  const [mensagens, setMensagens] = useState<ChatInternoMensagem[]>([]);
  const [conteudo, setConteudo] = useState("");
  const [busca, setBusca] = useState("");
  const [carregandoEstrutura, setCarregandoEstrutura] = useState(true);
  const [carregandoMensagens, setCarregandoMensagens] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState("");
  const [listaMobileAberta, setListaMobileAberta] = useState(true);
  const [modalGrupoAberto, setModalGrupoAberto] = useState(false);
  const [nomeGrupo, setNomeGrupo] = useState("");
  const [participantesGrupo, setParticipantesGrupo] = useState<number[]>([]);
  const [criandoGrupo, setCriandoGrupo] = useState(false);
  const fimRef = useRef<HTMLDivElement | null>(null);
  const primeiraCargaRef = useRef(true);

  const canalSelecionado = useMemo(
    () => canais.find((canal) => canal.id === canalId) ?? null,
    [canais, canalId],
  );

  const canaisDiretosPorUsuario = useMemo(() => {
    const mapa = new Map<number, ChatInternoCanal>();

    canais
      .filter((canal) => canal.tipo === "DIRETO")
      .forEach((canal) => {
        const outraPessoa = canal.membros.find((membro) => membro.id !== usuario.id);
        if (outraPessoa) mapa.set(outraPessoa.id, canal);
      });

    return mapa;
  }, [canais, usuario.id]);

  const conversasVisiveis = useMemo<ConversaUsuario[]>(() => {
    const termo = busca.trim().toLocaleLowerCase("pt-BR");

    return usuarios
      .filter(
        (pessoa) =>
          !termo || pessoa.nome.toLocaleLowerCase("pt-BR").includes(termo),
      )
      .map((pessoa) => ({
        pessoa,
        canal: canaisDiretosPorUsuario.get(pessoa.id) ?? null,
      }))
      .sort((a, b) => {
        const diferencaData = dataOrdenacao(b.canal) - dataOrdenacao(a.canal);
        if (diferencaData !== 0) return diferencaData;
        return a.pessoa.nome.localeCompare(b.pessoa.nome, "pt-BR");
      });
  }, [busca, canaisDiretosPorUsuario, usuarios]);

  const gruposVisiveis = useMemo(() => {
    const termo = busca.trim().toLocaleLowerCase("pt-BR");

    return ordenarGrupos(
      canais.filter(
        (canal) =>
          (canal.tipo === "GERAL" || canal.tipo === "GRUPO") &&
          (!termo || canal.nome.toLocaleLowerCase("pt-BR").includes(termo)),
      ),
    );
  }, [busca, canais]);

  const marcarComoLido = useCallback(async (id: number) => {
    try {
      await apiRequest<ChatInternoLeitura>(
        `/chat-interno/canais/${id}/marcar-lido`,
        { method: "POST" },
      );
      setCanais((atuais) =>
        atuais.map((canal) =>
          canal.id === id ? { ...canal, nao_lidas: 0 } : canal,
        ),
      );
      window.dispatchEvent(new Event(CHAT_UPDATE_EVENT));
    } catch {
      // A leitura será tentada novamente na próxima atualização automática.
    }
  }, []);

  const carregarCanais = useCallback(async (silencioso = false) => {
    if (!silencioso) setCarregandoEstrutura(true);

    try {
      const [novosUsuarios, novosCanais] = await Promise.all([
        apiRequest<ChatInternoUsuario[]>("/chat-interno/usuarios"),
        apiRequest<ChatInternoCanal[]>("/chat-interno/canais"),
      ]);

      setUsuarios(novosUsuarios);
      setCanais(novosCanais);
      setCanalId((atual) => {
        if (atual && novosCanais.some((canal) => canal.id === atual)) return atual;
        return novosCanais.find((canal) => canal.tipo === "DIRETO")?.id ?? null;
      });
      setErro("");
    } catch (error) {
      if (!silencioso) {
        setErro(
          error instanceof Error
            ? error.message
            : "Não foi possível carregar o chat interno.",
        );
      }
    } finally {
      if (!silencioso) setCarregandoEstrutura(false);
    }
  }, []);

  const carregarMensagens = useCallback(
    async (id: number, silencioso = false) => {
      if (!silencioso) setCarregandoMensagens(true);

      try {
        const dados = await apiRequest<ChatInternoMensagem[]>(
          `/chat-interno/canais/${id}/mensagens?limit=160`,
        );
        setMensagens(dados);
        setErro("");
        await marcarComoLido(id);
      } catch (error) {
        if (!silencioso) {
          setErro(
            error instanceof Error
              ? error.message
              : "Não foi possível carregar as mensagens.",
          );
        }
      } finally {
        if (!silencioso) setCarregandoMensagens(false);
      }
    },
    [marcarComoLido],
  );

  useEffect(() => {
    void carregarCanais();
  }, [carregarCanais]);

  useEffect(() => {
    if (!canalId) {
      setMensagens([]);
      return;
    }

    primeiraCargaRef.current = true;
    void carregarMensagens(canalId);

    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        void carregarMensagens(canalId, true);
        void carregarCanais(true);
      }
    }, 5000);

    return () => window.clearInterval(timer);
  }, [canalId, carregarCanais, carregarMensagens]);

  useEffect(() => {
    if (!mensagens.length) return;
    fimRef.current?.scrollIntoView({
      behavior: primeiraCargaRef.current ? "auto" : "smooth",
      block: "end",
    });
    primeiraCargaRef.current = false;
  }, [mensagens]);

  function mudarAba(novaAba: AbaChat) {
    setAba(novaAba);
    setBusca("");
    setCanalId(null);
    setMensagens([]);
    setConteudo("");
    setListaMobileAberta(true);
  }

  function selecionarCanal(canal: ChatInternoCanal) {
    setCanalId(canal.id);
    setListaMobileAberta(false);
    setConteudo("");
  }

  async function selecionarConversa(pessoa: ChatInternoUsuario) {
    const existente = canaisDiretosPorUsuario.get(pessoa.id);
    if (existente) {
      selecionarCanal(existente);
      return;
    }

    setErro("");
    try {
      const canal = await apiRequest<ChatInternoCanal>(
        "/chat-interno/diretos",
        {
          method: "POST",
          body: JSON.stringify({ usuario_id: pessoa.id }),
        },
      );

      setCanais((atuais) => [
        canal,
        ...atuais.filter((item) => item.id !== canal.id),
      ]);
      setCanalId(canal.id);
      setAba("CONVERSAS");
      setListaMobileAberta(false);
      setConteudo("");
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível acessar a conversa.",
      );
    }
  }

  function alternarParticipante(id: number) {
    setParticipantesGrupo((atuais) =>
      atuais.includes(id)
        ? atuais.filter((item) => item !== id)
        : [...atuais, id],
    );
  }

  function fecharModalGrupo() {
    if (criandoGrupo) return;
    setModalGrupoAberto(false);
    setNomeGrupo("");
    setParticipantesGrupo([]);
  }

  async function criarGrupo(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nome = nomeGrupo.trim();
    if (!nome || participantesGrupo.length === 0 || criandoGrupo) return;

    setCriandoGrupo(true);
    setErro("");
    try {
      const canal = await apiRequest<ChatInternoCanal>(
        "/chat-interno/grupos",
        {
          method: "POST",
          body: JSON.stringify({
            nome,
            usuario_ids: participantesGrupo,
          }),
        },
      );

      setCanais((atuais) => [canal, ...atuais]);
      setCanalId(canal.id);
      setAba("GRUPOS");
      setListaMobileAberta(false);
      setModalGrupoAberto(false);
      setNomeGrupo("");
      setParticipantesGrupo([]);
      window.dispatchEvent(new Event(CHAT_UPDATE_EVENT));
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível criar o grupo.",
      );
    } finally {
      setCriandoGrupo(false);
    }
  }

  async function enviarMensagem(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    const texto = conteudo.trim();
    if (!texto || enviando || !canalId) return;

    setEnviando(true);
    setErro("");
    try {
      const novaMensagem = await apiRequest<ChatInternoMensagem>(
        `/chat-interno/canais/${canalId}/mensagens`,
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
      await marcarComoLido(canalId);
      await carregarCanais(true);
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

  function avatarCanal(canal: ChatInternoCanal) {
    if (canal.tipo === "GERAL") return <Icon name="building" size={20} />;
    if (canal.tipo === "GRUPO") return <Icon name="team" size={20} />;

    const outraPessoa = canal.membros.find((membro) => membro.id !== usuario.id);
    if (outraPessoa?.foto_perfil) {
      return <img src={outraPessoa.foto_perfil} alt="" />;
    }
    return iniciais(outraPessoa?.nome ?? canal.nome);
  }

  let dataAnterior = "";
  const outraPessoaSelecionada = canalSelecionado?.membros.find(
    (membro) => membro.id !== usuario.id,
  );

  return (
    <div className="team-chat-page team-chat-page-refined">
      {erro && (
        <div className="team-chat-alert">
          <Alert>{erro}</Alert>
        </div>
      )}

      <section
        className={`team-chat-shell ${listaMobileAberta ? "team-chat-show-list" : "team-chat-show-conversation"}`}
        aria-label="Chat interno da empresa"
      >
        <aside className="team-chat-sidebar">
          <header className="team-chat-sidebar-header">
            <div>
              <span>Comunicação da equipe</span>
              <h1>Chat interno</h1>
            </div>
            <button
              className="team-chat-create-button"
              type="button"
              onClick={() => setModalGrupoAberto(true)}
              title="Criar grupo"
              aria-label="Criar grupo"
            >
              <Icon name="plus" size={20} />
            </button>
          </header>

          <label className="team-chat-search">
            <Icon name="search" size={18} />
            <input
              value={busca}
              onChange={(event) => setBusca(event.target.value)}
              placeholder={
                aba === "CONVERSAS"
                  ? "Buscar conversa..."
                  : "Buscar grupo..."
              }
            />
          </label>

          <div className="team-chat-tabs" role="tablist" aria-label="Tipo de conversa">
            <button
              className={aba === "CONVERSAS" ? "team-chat-tab-active" : ""}
              type="button"
              onClick={() => mudarAba("CONVERSAS")}
              role="tab"
              aria-selected={aba === "CONVERSAS"}
            >
              Conversas
            </button>
            <button
              className={aba === "GRUPOS" ? "team-chat-tab-active" : ""}
              type="button"
              onClick={() => mudarAba("GRUPOS")}
              role="tab"
              aria-selected={aba === "GRUPOS"}
            >
              Grupos
            </button>
          </div>

          {carregandoEstrutura ? (
            <LoadingState label="Carregando equipe..." />
          ) : (
            <section className="team-chat-channel-section team-chat-channel-section-refined">
              <div className="team-chat-section-title">
                <strong>
                  {aba === "CONVERSAS" ? "Todas as conversas" : "Grupos da empresa"}
                </strong>
                <span>
                  {aba === "CONVERSAS"
                    ? conversasVisiveis.length
                    : gruposVisiveis.length}
                </span>
              </div>

              <div className="team-chat-channel-list">
                {aba === "CONVERSAS" ? (
                  conversasVisiveis.length === 0 ? (
                    <div className="team-chat-list-empty">
                      <Icon name="chat" size={26} />
                      <strong>Nenhum usuário encontrado</strong>
                      <p>Não há outra pessoa ativa disponível nesta empresa.</p>
                    </div>
                  ) : (
                    conversasVisiveis.map(({ pessoa, canal }) => (
                      <button
                        className={`team-chat-channel ${canal?.id === canalId ? "team-chat-channel-active" : ""}`}
                        type="button"
                        key={pessoa.id}
                        onClick={() => void selecionarConversa(pessoa)}
                      >
                        <span
                          className={`team-chat-channel-avatar avatar-${pessoa.cargo.toLowerCase()}`}
                        >
                          {pessoa.foto_perfil ? (
                            <img src={pessoa.foto_perfil} alt="" />
                          ) : (
                            iniciais(pessoa.nome)
                          )}
                        </span>
                        <span className="team-chat-channel-copy">
                          <span>
                            <strong>{pessoa.nome}</strong>
                            {canal?.ultima_mensagem && (
                              <time dateTime={canal.ultima_mensagem.created_at}>
                                {formatarHorario(canal.ultima_mensagem.created_at)}
                              </time>
                            )}
                          </span>
                          <span>
                            <small>{resumoMensagem(canal)}</small>
                            {canal && canal.nao_lidas > 0 && (
                              <b>{canal.nao_lidas > 99 ? "99+" : canal.nao_lidas}</b>
                            )}
                          </span>
                        </span>
                      </button>
                    ))
                  )
                ) : gruposVisiveis.length === 0 ? (
                  <div className="team-chat-list-empty">
                    <Icon name="team" size={26} />
                    <strong>Nenhum grupo encontrado</strong>
                    <p>Use o botão + para criar um grupo com a equipe.</p>
                  </div>
                ) : (
                  gruposVisiveis.map((canal) => (
                    <button
                      className={`team-chat-channel ${canal.id === canalId ? "team-chat-channel-active" : ""}`}
                      type="button"
                      key={canal.id}
                      onClick={() => selecionarCanal(canal)}
                    >
                      <span
                        className={`team-chat-channel-avatar team-chat-channel-avatar-${canal.tipo.toLowerCase()}`}
                      >
                        {avatarCanal(canal)}
                      </span>
                      <span className="team-chat-channel-copy">
                        <span>
                          <strong>{canal.nome}</strong>
                          {canal.ultima_mensagem && (
                            <time dateTime={canal.ultima_mensagem.created_at}>
                              {formatarHorario(canal.ultima_mensagem.created_at)}
                            </time>
                          )}
                        </span>
                        <span>
                          <small>{resumoMensagem(canal)}</small>
                          {canal.nao_lidas > 0 && (
                            <b>{canal.nao_lidas > 99 ? "99+" : canal.nao_lidas}</b>
                          )}
                        </span>
                      </span>
                    </button>
                  ))
                )}
              </div>
            </section>
          )}
        </aside>

        <main className="team-chat-conversation">
          {!canalSelecionado ? (
            <div className="team-chat-welcome">
              <span>
                <Icon name={aba === "CONVERSAS" ? "chat" : "team"} size={34} />
              </span>
              <h2>
                {aba === "CONVERSAS"
                  ? "Escolha uma conversa"
                  : "Escolha um grupo"}
              </h2>
              <p>
                {aba === "CONVERSAS"
                  ? "Selecione qualquer usuário da empresa para conversar."
                  : "Abra o Geral da empresa ou um dos grupos criados."}
              </p>
            </div>
          ) : (
            <>
              <header className="team-chat-conversation-header">
                <button
                  className="team-chat-mobile-back"
                  type="button"
                  onClick={() => setListaMobileAberta(true)}
                  aria-label="Voltar para conversas"
                >
                  <Icon name="arrow-left" size={20} />
                </button>
                <span
                  className={`team-chat-channel-avatar team-chat-channel-avatar-${canalSelecionado.tipo.toLowerCase()} ${outraPessoaSelecionada ? `avatar-${outraPessoaSelecionada.cargo.toLowerCase()}` : ""}`}
                >
                  {avatarCanal(canalSelecionado)}
                </span>
                <div>
                  <strong>{canalSelecionado.nome}</strong>
                  <span>
                    {canalSelecionado.tipo === "DIRETO"
                      ? cargoLabel[outraPessoaSelecionada?.cargo ?? "FUNCIONARIO"]
                      : `${canalSelecionado.membros.length} participantes`}
                  </span>
                </div>
                <span className="team-chat-live-status">
                  <i /> Atualização automática
                </span>
              </header>

              <div className="team-chat-messages" aria-live="polite">
                {carregandoMensagens ? (
                  <LoadingState label="Carregando mensagens..." />
                ) : mensagens.length === 0 ? (
                  <div className="team-chat-message-empty">
                    <span>
                      <Icon name="chat" size={30} />
                    </span>
                    <strong>Nenhuma mensagem ainda</strong>
                    <p>Escreva abaixo para conversar com {canalSelecionado.nome}.</p>
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
                          <div className="team-chat-date">
                            <span>{dataAtual}</span>
                          </div>
                        )}
                        <article
                          className={`team-chat-message ${propria ? "team-chat-message-own" : ""}`}
                        >
                          <span
                            className={`team-chat-avatar avatar-${mensagem.autor.cargo.toLowerCase()}`}
                          >
                            {mensagem.autor.foto_perfil ? (
                              <img src={mensagem.autor.foto_perfil} alt="" />
                            ) : (
                              iniciais(mensagem.autor.nome)
                            )}
                          </span>
                          <div className="team-chat-bubble">
                            <div className="team-chat-message-meta">
                              <strong>{propria ? "Você" : mensagem.autor.nome}</strong>
                              <span
                                className={`team-chat-role role-badge-${mensagem.autor.cargo.toLowerCase()}`}
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

              <form className="team-chat-composer" onSubmit={enviarMensagem}>
                <textarea
                  value={conteudo}
                  onChange={(event) => setConteudo(event.target.value)}
                  onKeyDown={tratarTecla}
                  placeholder={`Mensagem para ${canalSelecionado.nome}...`}
                  maxLength={2000}
                  rows={1}
                  disabled={enviando}
                  aria-label={`Mensagem para ${canalSelecionado.nome}`}
                />
                <div className="team-chat-composer-info">
                  <span>Enter envia · Shift + Enter quebra a linha</span>
                  <span>{conteudo.length}/2000</span>
                </div>
                <button
                  className="button button-primary team-chat-send"
                  type="submit"
                  disabled={!conteudo.trim() || enviando}
                >
                  <Icon name="send" size={18} />
                  <span>{enviando ? "Enviando..." : "Enviar"}</span>
                </button>
              </form>
            </>
          )}
        </main>
      </section>

      <Modal
        open={modalGrupoAberto}
        title="Criar grupo"
        subtitle="Escolha um nome e as pessoas que participarão da conversa."
        onClose={fecharModalGrupo}
        size="medium"
      >
        <form className="team-chat-group-form" onSubmit={criarGrupo}>
          <label>
            Nome do grupo
            <input
              value={nomeGrupo}
              onChange={(event) => setNomeGrupo(event.target.value)}
              placeholder="Ex.: Equipe da manhã"
              maxLength={80}
              autoFocus
            />
          </label>

          <div className="team-chat-group-participants">
            <div className="team-chat-section-title">
              <strong>Participantes</strong>
              <span>{participantesGrupo.length} selecionados</span>
            </div>
            <div className="team-chat-group-user-list">
              {usuarios.map((pessoa) => (
                <label className="team-chat-group-user" key={pessoa.id}>
                  <input
                    type="checkbox"
                    checked={participantesGrupo.includes(pessoa.id)}
                    onChange={() => alternarParticipante(pessoa.id)}
                  />
                  <span
                    className={`team-chat-avatar avatar-${pessoa.cargo.toLowerCase()}`}
                  >
                    {pessoa.foto_perfil ? (
                      <img src={pessoa.foto_perfil} alt="" />
                    ) : (
                      iniciais(pessoa.nome)
                    )}
                  </span>
                  <span>
                    <strong>{pessoa.nome}</strong>
                    <small>{cargoLabel[pessoa.cargo]}</small>
                  </span>
                </label>
              ))}
            </div>
          </div>

          <div className="modal-actions">
            <button
              className="button button-secondary"
              type="button"
              onClick={fecharModalGrupo}
              disabled={criandoGrupo}
            >
              Cancelar
            </button>
            <button
              className="button button-primary"
              type="submit"
              disabled={
                !nomeGrupo.trim() ||
                participantesGrupo.length === 0 ||
                criandoGrupo
              }
            >
              <Icon name="team" size={18} />
              {criandoGrupo ? "Criando..." : "Criar grupo"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
