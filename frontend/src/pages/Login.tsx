import { useEffect, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { Icon } from "../components/Icon";
import { LoadingState } from "../components/UI";
import { apiRequest, restoreRememberedSession } from "../services/api";
import { getCompanyId, getToken, saveSession } from "../services/auth";

interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export function Login() {
  const navigate = useNavigate();
  const [empresaId, setEmpresaId] = useState(getCompanyId());
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [manterConectado, setManterConectado] = useState(false);
  const [mostrarSenha, setMostrarSenha] = useState(false);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);
  const [verificandoSessao, setVerificandoSessao] = useState(!getToken());
  const [sessaoRestaurada, setSessaoRestaurada] = useState(Boolean(getToken()));

  useEffect(() => {
    if (!verificandoSessao) return;

    let ativo = true;
    void restoreRememberedSession().then((restaurada) => {
      if (!ativo) return;
      setSessaoRestaurada(restaurada);
      setVerificandoSessao(false);
    });

    return () => {
      ativo = false;
    };
  }, [verificandoSessao]);

  if (verificandoSessao) {
    return (
      <main className="app-loading">
        <LoadingState label="Verificando sua sessão..." />
      </main>
    );
  }

  if (sessaoRestaurada || getToken()) {
    return <Navigate to="/dashboard" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro("");
    setCarregando(true);

    try {
      const response = await apiRequest<LoginResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({
          empresa_id: Number(empresaId),
          email: email.trim(),
          senha,
          manter_conectado: manterConectado,
        }),
      });

      saveSession(response.access_token, empresaId);
      navigate("/dashboard", { replace: true });
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível realizar o login.");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-brand" aria-label="Apresentação do FlowDeskIA">
        <div className="brand-content">
          <div className="brand-logo">F</div>
          <span className="brand-eyebrow">Gestão inteligente</span>
          <h1>FlowDeskIA</h1>
          <p>
            Atendimento, agenda e relacionamento com clientes organizados em uma
            única plataforma.
          </p>
          <div className="brand-features">
            <span>Agenda integrada</span>
            <span>Atendimento centralizado</span>
            <span>Automação com IA</span>
          </div>
        </div>
      </section>

      <section className="login-form-area">
        <form className="login-card" onSubmit={handleSubmit}>
          <header>
            <span className="login-label">Acesso ao sistema</span>
            <h2>Bem-vindo de volta</h2>
            <p>Agenda, clientes e atendimento em um só lugar.</p>
          </header>

          <label>
            Empresa ID
            <input
              type="number"
              min="1"
              inputMode="numeric"
              value={empresaId}
              onChange={(event) => setEmpresaId(event.target.value)}
              required
            />
          </label>

          <label>
            E-mail
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="seuemail@exemplo.com"
              required
            />
          </label>

          <label>
            Senha
            <div className="password-field">
              <input
                type={mostrarSenha ? "text" : "password"}
                autoComplete="current-password"
                value={senha}
                onChange={(event) => setSenha(event.target.value)}
                placeholder="Digite sua senha"
                required
              />
              <button
                className="password-toggle"
                type="button"
                onClick={() => setMostrarSenha((atual) => !atual)}
                aria-label={mostrarSenha ? "Ocultar senha" : "Mostrar senha"}
              >
                <Icon name="eye" size={18} />
              </button>
            </div>
          </label>

          <div className="login-options">
            <label className="remember-device-option">
              <input
                className="remember-device-input"
                type="checkbox"
                checked={manterConectado}
                onChange={(event) => setManterConectado(event.target.checked)}
              />
              <span className="remember-device-box" aria-hidden="true" />
              <span>Lembre de mim</span>
            </label>

            <Link className="auth-link" to="/recuperar-senha">
              Esqueceu sua senha?
            </Link>
          </div>

          {erro && <div className="alert alert-error">{erro}</div>}

          <button className="button button-primary button-full" type="submit" disabled={carregando}>
            {carregando ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </section>
    </main>
  );
}
