import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";
import { Icon } from "../components/Icon";
import { apiRequest } from "../services/api";

interface MessageResponse {
  mensagem: string;
}

export function RedefinirSenha() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [novaSenha, setNovaSenha] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [mostrarSenha, setMostrarSenha] = useState(false);
  const [erro, setErro] = useState("");
  const [mensagem, setMensagem] = useState("");
  const [carregando, setCarregando] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro("");
    setMensagem("");

    if (!token) {
      setErro("O link de recuperação está incompleto.");
      return;
    }

    if (novaSenha !== confirmacao) {
      setErro("As senhas informadas não coincidem.");
      return;
    }

    setCarregando(true);

    try {
      const response = await apiRequest<MessageResponse>(
        "/auth/redefinir-senha",
        {
          method: "POST",
          body: JSON.stringify({ token, nova_senha: novaSenha }),
        },
      );
      setMensagem(response.mensagem);
      setNovaSenha("");
      setConfirmacao("");
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível redefinir a senha.",
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
            <h2>Definir nova senha</h2>
            <p>Crie uma senha com pelo menos 8 caracteres.</p>
          </header>

          {!token && (
            <div className="alert alert-error">
              O link de recuperação está incompleto. Solicite um novo link.
            </div>
          )}

          <label>
            Nova senha
            <div className="password-field">
              <input
                type={mostrarSenha ? "text" : "password"}
                autoComplete="new-password"
                minLength={8}
                value={novaSenha}
                onChange={(event) => setNovaSenha(event.target.value)}
                placeholder="Digite a nova senha"
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

          <label>
            Confirmar nova senha
            <input
              type={mostrarSenha ? "text" : "password"}
              autoComplete="new-password"
              minLength={8}
              value={confirmacao}
              onChange={(event) => setConfirmacao(event.target.value)}
              placeholder="Repita a nova senha"
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

          {!mensagem ? (
            <button
              className="button button-primary button-full"
              type="submit"
              disabled={carregando || !token}
            >
              {carregando ? "Salvando..." : "Salvar nova senha"}
            </button>
          ) : (
            <Link className="button button-primary button-full" to="/login">
              Ir para o login
            </Link>
          )}

          {!mensagem && (
            <Link className="auth-back-link" to="/login">
              <Icon name="arrow-left" size={16} />
              Voltar para o login
            </Link>
          )}
        </form>
      </section>
    </main>
  );
}
