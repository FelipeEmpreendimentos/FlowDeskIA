import { useCallback, useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router";
import { apiRequest } from "../services/api";
import { clearSession } from "../services/auth";
import type { AppOutletContext, UsuarioLogado } from "../types";
import { Icon, type IconName } from "./Icon";
import { LoadingState } from "./UI";

const menu: Array<{ to: string; label: string; icon: IconName }> = [
  { to: "/dashboard", label: "Visão geral", icon: "dashboard" },
  { to: "/agenda", label: "Agenda", icon: "calendar" },
  { to: "/clientes", label: "Clientes", icon: "users" },
  { to: "/veiculos", label: "Veículos", icon: "car" },
  { to: "/servicos", label: "Serviços", icon: "services" },
  { to: "/conversas", label: "Conversas", icon: "chat" },
  { to: "/equipe", label: "Equipe", icon: "team" },
  { to: "/configuracoes", label: "Configurações", icon: "settings" },
];

export function AppLayout() {
  const navigate = useNavigate();
  const [usuario, setUsuario] = useState<UsuarioLogado | null>(null);
  const [erro, setErro] = useState("");
  const [menuAberto, setMenuAberto] = useState(false);

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

  return (
    <div className="app-shell">
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
          {menu.map((item) => (
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
  );
}
