import { useCallback, useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router";
import { Icon, type IconName } from "./Icon";
import { clearSuperAdminSession } from "../services/superAdminAuth";
import { superAdminApiRequest } from "../services/superAdminApi";
import type {
  SuperAdminOutletContext,
  SuperAdminUsuario,
} from "../types/superAdmin";

const menu: Array<{ to: string; label: string; icon: IconName }> = [
  { to: "/super-admin/dashboard", label: "Visão geral", icon: "dashboard" },
  { to: "/super-admin/empresas", label: "Empresas", icon: "building" },
  { to: "/super-admin/simulador-ia", label: "Simulador IA", icon: "bot" },
  { to: "/super-admin/planos", label: "Planos", icon: "services" },
  { to: "/super-admin/auditoria", label: "Auditoria", icon: "clock" },
];

export function SuperAdminLayout() {
  const navigate = useNavigate();
  const [usuario, setUsuario] = useState<SuperAdminUsuario | null>(null);
  const [erro, setErro] = useState("");
  const [menuAberto, setMenuAberto] = useState(false);

  const atualizarUsuario = useCallback(async () => {
    try {
      const data = await superAdminApiRequest<SuperAdminUsuario>("/auth/me");
      setUsuario(data);
      setErro("");
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível carregar o Super Admin.",
      );
    }
  }, []);

  useEffect(() => {
    void atualizarUsuario();
  }, [atualizarUsuario]);

  function sair() {
    clearSuperAdminSession();
    navigate("/super-admin/login", { replace: true });
  }

  if (!usuario && !erro) {
    return <main className="super-admin-loading">Preparando o painel...</main>;
  }

  if (!usuario) {
    return (
      <main className="super-admin-loading">
        <section className="super-admin-fatal">
          <h1>Não foi possível abrir o painel</h1>
          <p>{erro}</p>
          <button type="button" onClick={sair}>
            Voltar ao login
          </button>
        </section>
      </main>
    );
  }

  const context: SuperAdminOutletContext = { usuario, atualizarUsuario };

  return (
    <div className="super-admin-shell">
      <button
        className="super-admin-mobile-menu"
        type="button"
        onClick={() => setMenuAberto(true)}
        aria-label="Abrir menu"
      >
        <Icon name="menu" />
      </button>

      {menuAberto && (
        <button
          className="super-admin-overlay"
          type="button"
          onClick={() => setMenuAberto(false)}
          aria-label="Fechar menu"
        />
      )}

      <aside className={`super-admin-sidebar ${menuAberto ? "is-open" : ""}`}>
        <div className="super-admin-brand">
          <span>F</span>
          <div>
            <strong>FlowDeskIA</strong>
            <small>Controle da plataforma</small>
          </div>
          <button
            className="super-admin-sidebar-close"
            type="button"
            onClick={() => setMenuAberto(false)}
            aria-label="Fechar menu"
          >
            <Icon name="close" size={18} />
          </button>
        </div>

        <div className="super-admin-owner-badge">
          <Icon name="lock" size={16} />
          Acesso proprietário
        </div>

        <nav>
          {menu.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setMenuAberto(false)}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              <Icon name={item.icon} size={18} />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="super-admin-profile">
          <span>{usuario.nome.charAt(0).toUpperCase()}</span>
          <div>
            <strong>{usuario.nome}</strong>
            <small>SUPER ADMIN</small>
          </div>
        </div>

        <button className="super-admin-logout" type="button" onClick={sair}>
          <Icon name="logout" size={18} />
          Sair do painel
        </button>
      </aside>

      <main className="super-admin-content">
        <Outlet context={context} />
      </main>
    </div>
  );
}
