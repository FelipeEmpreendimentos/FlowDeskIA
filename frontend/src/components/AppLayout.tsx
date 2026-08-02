import { useCallback, useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router";
import {
  APP_TOAST_EVENT,
  apiRequest,
  type AppToastEventDetail,
} from "../services/api";
import { clearSession } from "../services/auth";
import type {
  AppOutletContext,
  CargoUsuario,
  Notificacao,
  UsuarioLogado,
} from "../types";
import type { CurrentAccess, ModuleCode } from "../types/accessControl";
import type { ChatInternoResumo } from "../types/internal-chat";
import { Icon, type IconName } from "./Icon";
import { AppToast, LoadingState } from "./UI";

const CHAT_UPDATE_EVENT = "flowdesk:chat-update";

interface MenuItem {
  to: string;
  label: string;
  labelFuncionario?: string;
  icon: IconName;
  module?: ModuleCode;
}

interface MenuGroup {
  label: string;
  items: MenuItem[];
}

const menuGroups: MenuGroup[] = [
  {
    label: "Principal",
    items: [
      { to: "/dashboard", label: "Visão geral", icon: "dashboard" },
      {
        to: "/agenda",
        label: "Agenda",
        labelFuncionario: "Minha agenda",
        icon: "calendar",
        module: "AGENDA",
      },
      {
        to: "/chat-interno",
        label: "Chat interno",
        icon: "chat",
        module: "CHAT_INTERNO",
      },
    ],
  },
  {
    label: "Atendimento",
    items: [
      {
        to: "/conversas",
        label: "Conversas",
        icon: "chat",
        module: "CONVERSAS",
      },
      {
        to: "/clientes",
        label: "Clientes",
        icon: "users",
        module: "CLIENTES",
      },
      {
        to: "/veiculos",
        label: "Veículos",
        icon: "car",
        module: "VEICULOS",
      },
      {
        to: "/servicos",
        label: "Serviços",
        icon: "services",
        module: "SERVICOS",
      },
    ],
  },
  {
    label: "Gestão",
    items: [
      {
        to: "/financeiro",
        label: "Financeiro",
        icon: "finance",
        module: "FINANCEIRO",
      },
      {
        to: "/relatorios",
        label: "Relatórios",
        icon: "dashboard",
        module: "RELATORIOS",
      },
      {
        to: "/equipe",
        label: "Equipe",
        icon: "team",
        module: "EQUIPE",
      },
    ],
  },
];

const cargoLabel: Record<CargoUsuario, string> = {
  ADMIN: "Administrador",
  GERENTE: "Gerente",
  FUNCIONARIO: "Funcionário",
};

const rotasDetalheConfiguracoes = new Set([
  "/configuracoes/dados",
  "/configuracoes/agenda",
  "/configuracoes/acessos",
  "/atividades",
  "/plano-consumo",
]);

export function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const rotaAntesNotificacoes = useRef("/dashboard");
  const [usuario, setUsuario] = useState<UsuarioLogado | null>(null);
  const [modulos, setModulos] = useState<Partial<Record<ModuleCode, boolean>>>({});
  const [erro, setErro] = useState("");
  const [menuAberto, setMenuAberto] = useState(false);
  const [toast, setToast] = useState<AppToastEventDetail | null>(null);
  const [notificacoesNaoLidas, setNotificacoesNaoLidas] = useState(0);
  const [chatNaoLidas, setChatNaoLidas] = useState(0);

  const atualizarUsuario = useCallback(async () => {
    try {
      const [dadosUsuario, dadosAcesso] = await Promise.all([
        apiRequest<UsuarioLogado>("/auth/me"),
        apiRequest<CurrentAccess>("/acessos/me"),
      ]);
      setUsuario(dadosUsuario);
      setModulos(dadosAcesso.modules);
      setErro("");
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível carregar o usuário.",
      );
    }
  }, []);

  const atualizarIndicadores = useCallback(async () => {
    if (!usuario) return;

    const [notificacoesResult, chatResult] = await Promise.allSettled([
      apiRequest<Notificacao[]>("/notificacoes?somente_nao_lidas=true"),
      modulos.CHAT_INTERNO
        ? apiRequest<ChatInternoResumo>("/chat-interno/resumo")
        : Promise.resolve<ChatInternoResumo>({
            nao_lidas: 0,
            ultima_mensagem_id: null,
          }),
    ]);

    if (notificacoesResult.status === "fulfilled") {
      setNotificacoesNaoLidas(notificacoesResult.value.length);
    }
    if (chatResult.status === "fulfilled") {
      setChatNaoLidas(chatResult.value.nao_lidas);
    }
  }, [modulos.CHAT_INTERNO, usuario]);

  useEffect(() => {
    void atualizarUsuario();
  }, [atualizarUsuario]);

  useEffect(() => {
    if (location.pathname !== "/notificacoes") {
      rotaAntesNotificacoes.current = location.pathname;
    }
  }, [location.pathname]);

  useEffect(() => {
    function receberToast(event: Event) {
      const customEvent = event as CustomEvent<AppToastEventDetail>;
      if (!customEvent.detail?.message) return;
      setToast(customEvent.detail);
    }

    window.addEventListener(APP_TOAST_EVENT, receberToast);
    return () => window.removeEventListener(APP_TOAST_EVENT, receberToast);
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 4500);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    if (!usuario) return;

    void atualizarIndicadores();
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        void atualizarIndicadores();
      }
    }, 15000);

    const atualizarChat = () => void atualizarIndicadores();
    window.addEventListener(CHAT_UPDATE_EVENT, atualizarChat);

    return () => {
      window.clearInterval(timer);
      window.removeEventListener(CHAT_UPDATE_EVENT, atualizarChat);
    };
  }, [usuario, atualizarIndicadores]);

  useEffect(() => {
    if (usuario) void atualizarIndicadores();
  }, [location.pathname, usuario, atualizarIndicadores]);

  function sair() {
    clearSession();
    navigate("/login", { replace: true });
  }

  function alternarNotificacoes() {
    if (location.pathname === "/notificacoes") {
      navigate(rotaAntesNotificacoes.current || "/dashboard");
      return;
    }

    rotaAntesNotificacoes.current = location.pathname;
    navigate("/notificacoes");
  }

  function voltarDaTelaAtual() {
    if (location.pathname === "/notificacoes") {
      navigate(rotaAntesNotificacoes.current || "/dashboard");
      return;
    }

    navigate("/configuracoes");
  }

  if (!usuario && !erro) {
    return (
      <main className="app-loading">
        <LoadingState label="Preparando o FlowDeskIA..." />
      </main>
    );
  }

  if (!usuario) {
    return (
      <main className="app-loading">
        <div className="fatal-card">
          <h1>Não foi possível abrir o sistema</h1>
          <p>{erro}</p>
          <button className="button button-primary" type="button" onClick={sair}>
            Voltar ao login
          </button>
        </div>
      </main>
    );
  }

  const context: AppOutletContext = {
    usuario,
    modulos,
    atualizarUsuario,
  };
  const routeSection = location.pathname.split("/").filter(Boolean)[0] ?? "dashboard";
  const roleClass = `role-${usuario.cargo.toLowerCase()}`;
  const routeClass = `route-${routeSection.replaceAll("_", "-")}`;
  const gruposDisponiveis = menuGroups
    .map((group) => ({
      ...group,
      items: group.items.filter(
        (item) => !item.module || Boolean(modulos[item.module]),
      ),
    }))
    .filter((group) => group.items.length > 0);
  const configuracoesLabel =
    usuario.cargo === "FUNCIONARIO" ? "Minha conta" : "Configurações";
  const notificacoesAbertas = location.pathname === "/notificacoes";
  const detalheConfiguracoes = rotasDetalheConfiguracoes.has(location.pathname);
  const exibirRetornoContextual = notificacoesAbertas || detalheConfiguracoes;

  return (
    <>
      <div className={`app-shell ${roleClass} ${routeClass}`}>
        <button
          className="mobile-menu-button"
          type="button"
          onClick={() => setMenuAberto(true)}
          aria-label="Abrir menu"
        >
          <Icon name="menu" />
        </button>

        <button
          type="button"
          className={`global-notification-button ${
            notificacoesAbertas ? "global-notification-button-active" : ""
          }`}
          onClick={alternarNotificacoes}
          aria-pressed={notificacoesAbertas}
          aria-label={
            notificacoesAbertas
              ? "Fechar notificações e voltar"
              : notificacoesNaoLidas
                ? `${notificacoesNaoLidas} notificações não lidas`
                : "Abrir notificações"
          }
          title={notificacoesAbertas ? "Fechar notificações" : "Notificações"}
        >
          <Icon name="bell" size={20} />
          {notificacoesNaoLidas > 0 && (
            <span>{notificacoesNaoLidas > 99 ? "99+" : notificacoesNaoLidas}</span>
          )}
        </button>

        {menuAberto && (
          <button
            className="sidebar-overlay"
            type="button"
            onClick={() => setMenuAberto(false)}
            aria-label="Fechar menu"
          />
        )}

        <aside className={`sidebar ${menuAberto ? "sidebar-open" : ""}`}>
          <div className="sidebar-brand">
            <div className="sidebar-logo">F</div>
            <div>
              <strong>FlowDeskIA</strong>
              <span>Gestão inteligente</span>
            </div>
            <button
              className="sidebar-close"
              type="button"
              onClick={() => setMenuAberto(false)}
              aria-label="Fechar menu"
            >
              <Icon name="close" />
            </button>
          </div>

          <nav className="sidebar-nav" aria-label="Menu principal">
            {gruposDisponiveis.map((group) => (
              <div className="sidebar-nav-group" key={group.label}>
                <span className="sidebar-nav-label">{group.label}</span>
                <div className="sidebar-nav-items">
                  {group.items.map((item) => {
                    const label =
                      usuario.cargo === "FUNCIONARIO" && item.labelFuncionario
                        ? item.labelFuncionario
                        : item.label;
                    const badge = item.to === "/chat-interno" ? chatNaoLidas : 0;

                    return (
                      <NavLink
                        key={item.to}
                        to={item.to}
                        onClick={() => setMenuAberto(false)}
                        className={({ isActive }) =>
                          `nav-item ${isActive ? "nav-item-active" : ""}`
                        }
                      >
                        <Icon name={item.icon} size={19} />
                        <span>{label}</span>
                        {badge > 0 && (
                          <span className="nav-item-badge">
                            {badge > 99 ? "99+" : badge}
                          </span>
                        )}
                      </NavLink>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>

          <div className="sidebar-footer">
            <NavLink
              to="/configuracoes"
              onClick={() => setMenuAberto(false)}
              className={({ isActive }) =>
                `nav-item sidebar-settings-link ${isActive ? "nav-item-active" : ""}`
              }
            >
              <Icon
                name={usuario.cargo === "FUNCIONARIO" ? "users" : "settings"}
                size={19}
              />
              <span>{configuracoesLabel}</span>
            </NavLink>

            <div className="sidebar-user">
              <span className="sidebar-user-avatar">
                {usuario.nome.charAt(0).toUpperCase()}
              </span>
              <div>
                <strong>{usuario.nome}</strong>
                <span>{cargoLabel[usuario.cargo]}</span>
              </div>
            </div>

            <button className="logout-button" type="button" onClick={sair}>
              <Icon name="logout" size={18} />
              Sair da conta
            </button>
          </div>
        </aside>

        <main
          className={`app-content ${
            exibirRetornoContextual ? "app-content-with-context-back" : ""
          }`}
        >
          {exibirRetornoContextual && (
            <div className="context-back-bar">
              <button
                className="context-back-button"
                type="button"
                onClick={voltarDaTelaAtual}
              >
                <Icon name="arrow-left" size={18} />
                <span>
                  {notificacoesAbertas ? "Voltar" : "Voltar para configurações"}
                </span>
              </button>
            </div>
          )}
          <Outlet context={context} />
        </main>
      </div>

      {toast && (
        <AppToast
          type={toast.type}
          title={toast.title}
          message={toast.message}
          onClose={() => setToast(null)}
        />
      )}
    </>
  );
}
