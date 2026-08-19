import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import { Icon } from "../components/Icon";
import { apiRequest } from "../services/api";
import { getCompanyId } from "../services/auth";

interface RecuperarSenhaResponse {
  mensagem: string;
}

const MAX_EMPRESA_ID_DIGITS = 8;

function normalizarEmpresaId(value: string): string {
  return value.replace(/\D/g, "").slice(0, MAX_EMPRESA_ID_DIGITS);
}

export function RecuperarSenha() {
  const [empresaId, setEmpresaId] = useState(() => normalizarEmpresaId(getCompanyId()));
  const [email, setEmail] = useState("");
  const [erro, setErro] = useState("");
  const [mensagem, setMensagem] = useState("");
  const [carregando, setCarregando] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro("");
    setMensagem("");

    const empresaIdNormalizado = normalizarEmpresaId(empresaId);
    if (!empresaIdNormalizado || Number(empresaIdNormalizado) < 1) {
      setErro("Informe um número de empresa válido.");
      return;
    }

    setCarregando(true);

    try {
      const response = await apiRequest<RecuperarSenhaResponse>(
        "/auth/recuperar-senha",
        {
          method: "POST",
          body: JSON.stringify({
            empresa_id: Number(empresaIdNormalizado),
            email: email.trim(),
          }),
        },
      );

      setMensagem(response.mensagem);
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível solicitar a recuperação da senha.",
      );
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
            <span className="login-label">Segurança da conta</span>
            <h2>Recuperar senha</h2>
            <p>Informe o Empresa ID e o e-mail da sua conta.</p>
          </header>

          <label>
            Empresa ID
            <input
              type="text"
              inputMode="numeric"
              maxLength={MAX_EMPRESA_ID_DIGITS}
              pattern="[0-9]{1,8}"
              value={empresaId}
              onChange={(event) => setEmpresaId(normalizarEmpresaId(event.target.value))}
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

          {erro && <div className="alert alert-error">{erro}</div>}

          {mensagem && (
            <div className="alert alert-success auth-success">
              <Icon name="check" size={18} />
              <span>{mensagem}</span>
            </div>
          )}

          <button
            className="button button-primary button-full"
            type="submit"
            disabled={carregando}
          >
            {carregando ? "Enviando..." : "Recuperar senha"}
          </button>

          <Link className="auth-back-link" to="/login">
            <Icon name="arrow-left" size={16} />
            Voltar para o login
          </Link>
        </form>
      </section>
    </main>
  );
}
