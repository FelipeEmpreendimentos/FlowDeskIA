import { useCallback, useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router";
import {
  APP_TOAST_EVENT,
  apiRequest,
  type AppToastEventDetail,
} from "../services/api";
import { clearSession } from "../services/auth";
import type { AppOutletContext, CargoUsuario, UsuarioLogado } from "../types";
import { Icon, type IconName } from "./Icon";
import { AppToast, LoadingState } from "./UI";

interface MenuItem {
  to: string;
  label: string;
  icon: IconName;
  cargos?: CargoUsuario[];
}

const menu: MenuItem[] = [
  { to: "/dashboard", label: "Visão geral", icon: "dashboard" },
  { to: "/agenda", label: "Agenda", icon: "calendar" },
  { to: "/financeiro", label: "Financeiro", icon: "finance" },
  {
    to: "/relatorios",
    label: "Relatórios",
    icon: "dashboard",
    cargos: ["ADMIN", "GERENTE"],
  },
  { to: "/clientes", label: "Clientes", icon: "users" },
  { to: "/veiculos", label: "Veículos", icon: "car" },
  { to: "/servicos", label: "Serviços", icon: "services" },
  { to: "/conversas", label: "Conversas", icon: "chat" },
  { to: "/equipe", label: "Equipe", icon: "team" },
  {
    to: "/atividades",
    label: "Atividades",
    icon: "clock",
    cargos: ["ADMIN", "GERENTE"],
  },
  {
    to: "/plano-consumo",
    label: "Plano e consumo",
    icon: "lock",
    cargos: ["ADMIN"],
  },
  { to: "/configuracoes", label: "Configurações", icon: "settings" },
];

export function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [usuario, setUsuario] = useState<UsuarioLogado | null>(null);
  const [erro, setErro] = useState("");
  const [menuAberto, setMenuAberto] = useState(false);
  const [toast, setToast] = useState<AppToastEventDetail | null>(null);

  const atualizarUsuario = useCallback(async () => {
    try {
      const data = await apiRequest<UsuarioLogado>("/auth/me");
      setUsuario(data);
      setErro("");
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível carregar o usuário.");
    }
  }, []);

  useEffect(() => {
    void atualizarUsuario();
  }, [atualizarUsuario]);

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

  function sair() {
    clearSession();
    navigate("/login", { replace: true });
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
    atualizarUsuario,
  };
  const routeSection = location.pathname.split("/").filter(Boolean)[0] ?? "dashboard";
  const roleClass = `role-${usuario.cargo.toLowerCase()}`;
  const routeClass = `route-${routeSection.replaceAll("_", "-")}`;
  const menuDisponivel = menu.filter(
    (item) => !item.cargos || item.cargos.includes(usuario.cargo),
  );

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
            {menuDisponivel.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setMenuAberto(false)}
                className={({ isActive }) =>
                  `nav-item ${isActive ? "nav-item-active" : ""}`
                }
              >
                <Icon name={item.icon} size={19} />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>

          <div className="sidebar-user">
            <span className="sidebar-user-avatar">
              {usuario.nome.charAt(0).toUpperCase()}
            </span>
            <div>
              <strong>{usuario.nome}</strong>
              <span>{usuario.cargo}</span>
            </div>
          </div>

          <button className="logout-button" type="button" onClick={sair}>
            <Icon name="logout" size={18} />
            Sair da conta
          </button>
        </aside>

        <main className="app-content">
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
