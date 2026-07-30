import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";
import { Icon } from "../components/Icon";
import { superAdminApiRequest } from "../services/superAdminApi";
import {
  getSuperAdminToken,
  saveSuperAdminSession,
} from "../services/superAdminAuth";

interface LoginResponse {
  access_token: string;
  expires_in: number;
}

export function SuperAdminLogin() {
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [mostrarSenha, setMostrarSenha] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState("");

  if (getSuperAdminToken()) {
    return <Navigate to="/super-admin/dashboard" replace />;
  }

  async function entrar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setEnviando(true);
    setErro("");
    try {
      const response = await superAdminApiRequest<LoginResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: email.trim(), senha }),
      });
      saveSuperAdminSession(response.access_token);
      const state = location.state as { from?: string } | null;
      navigate(state?.from ?? "/super-admin/dashboard", { replace: true });
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível entrar.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <main className="super-admin-login-page">
      <section className="super-admin-login-brand">
        <div>
          <span className="super-admin-login-logo">F</span>
          <small>FLOWDESKIA PLATFORM</small>
          <h1>Controle total da sua operação SaaS.</h1>
          <p>
            Empresas, planos, testes, inteligência artificial, limites e auditoria
            em um ambiente separado e protegido.
          </p>
          <div className="super-admin-login-features">
            <span>Planos editáveis</span>
            <span>IA por empresa</span>
            <span>Auditoria completa</span>
          </div>
        </div>
      </section>

      <section className="super-admin-login-form-area">
        <form className="super-admin-login-card" onSubmit={entrar}>
          <header>
            <span>Painel proprietário</span>
            <h2>Super Admin</h2>
            <p>Use sua conta exclusiva da plataforma.</p>
          </header>

          {erro && <div className="super-admin-alert error">{erro}</div>}

          <label>
            E-mail
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
            />
          </label>

          <label>
            Senha
            <div className="super-admin-password-field">
              <input
                type={mostrarSenha ? "text" : "password"}
                value={senha}
                onChange={(event) => setSenha(event.target.value)}
                autoComplete="current-password"
                minLength={8}
                required
              />
              <button
                type="button"
                onClick={() => setMostrarSenha((value) => !value)}
                aria-label={mostrarSenha ? "Ocultar senha" : "Mostrar senha"}
              >
                <Icon name="eye" size={18} />
              </button>
            </div>
          </label>

          <button className="super-admin-primary-button" type="submit" disabled={enviando}>
            <Icon name="lock" size={18} />
            {enviando ? "Entrando..." : "Entrar no painel"}
          </button>

          <a className="super-admin-company-login-link" href="/login">
            Voltar ao login das empresas
          </a>
        </form>
      </section>
    </main>
  );
}
