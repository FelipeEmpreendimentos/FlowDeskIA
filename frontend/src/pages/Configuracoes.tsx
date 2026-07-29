import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { useOutletContext } from "react-router";
import { Icon } from "../components/Icon";
import { Modal } from "../components/Modal";
import { Alert, LoadingState, PageHeader, StatusBadge } from "../components/UI";
import { apiRequest } from "../services/api";
import type {
  AppOutletContext,
  ConfigIA,
  Empresa,
  Integracao,
  Notificacao,
} from "../types";
import { formatDateTime, normalizeNullable } from "../utils/format";

type AbaConfiguracao = "empresa" | "ia" | "notificacoes" | "seguranca";

interface EmpresaForm {
  nome: string;
  telefone: string;
  email: string;
  cidade: string;
  estado: string;
  timezone: string;
}

interface IAForm {
  nome_assistente: string;
  mensagem_boas_vindas: string;
  prompt: string;
  temperatura: string;
}

interface SenhaForm {
  senha_atual: string;
  nova_senha: string;
  confirmar_senha: string;
}

const API_ORIGIN = (
  import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api/v1"
).replace(/\/api\/v1\/?$/, "");

const fusosBrasil = [
  { value: "America/Sao_Paulo", label: "Brasília — UTC-3" },
  { value: "America/Manaus", label: "Manaus — UTC-4" },
  { value: "America/Rio_Branco", label: "Rio Branco — UTC-5" },
  { value: "America/Noronha", label: "Fernando de Noronha — UTC-2" },
];

function resolverLogoUrl(valor: string | null | undefined): string {
  if (!valor) return "";
  if (/^(https?:|data:|blob:)/i.test(valor)) return valor;
  return `${API_ORIGIN}${valor.startsWith("/") ? valor : `/${valor}`}`;
}

export function Configuracoes() {
  const { usuario, atualizarUsuario } = useOutletContext<AppOutletContext>();
  const [aba, setAba] = useState<AbaConfiguracao>("empresa");
  const [empresa, setEmpresa] = useState<Empresa | null>(null);
  const [empresaForm, setEmpresaForm] = useState<EmpresaForm>({
    nome: "",
    telefone: "",
    email: "",
    cidade: "",
    estado: "",
    timezone: "America/Sao_Paulo",
  });
  const [iaForm, setIaForm] = useState<IAForm>({
    nome_assistente: "Assistente",
    mensagem_boas_vindas: "",
    prompt: "",
    temperatura: "0.70",
  });
  const [notificacoes, setNotificacoes] = useState<Notificacao[]>([]);
  const [integracoes, setIntegracoes] = useState<Integracao[]>([]);
  const [senhaForm, setSenhaForm] = useState<SenhaForm>({
    senha_atual: "",
    nova_senha: "",
    confirmar_senha: "",
  });
  const inputLogoRef = useRef<HTMLInputElement | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [salvandoLogo, setSalvandoLogo] = useState(false);
  const [confirmarDadosEmpresa, setConfirmarDadosEmpresa] = useState(false);
  const [confirmarRemocaoLogo, setConfirmarRemocaoLogo] = useState(false);
  const [confirmarAlteracaoSenha, setConfirmarAlteracaoSenha] = useState(false);
  const [mostrarNovaSenha, setMostrarNovaSenha] = useState(false);
  const [mostrarConfirmacaoNovaSenha, setMostrarConfirmacaoNovaSenha] =
    useState(false);
  const [erroTemporario, setErroTemporario] = useState("");
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");

  const podeEditar = ["ADMIN", "GERENTE"].includes(usuario.cargo);

  async function carregar() {
    setCarregando(true);
    setErro("");

    try {
      const requests: [
        Promise<Empresa>,
        Promise<ConfigIA | null>,
        Promise<Notificacao[]>,
        Promise<Integracao[] | null>,
      ] = [
        apiRequest<Empresa>("/empresa"),
        apiRequest<ConfigIA | null>("/configuracoes/ia"),
        apiRequest<Notificacao[]>("/notificacoes"),
        ["ADMIN", "GERENTE"].includes(usuario.cargo)
          ? apiRequest<Integracao[]>("/configuracoes/integracoes")
          : Promise.resolve(null),
      ];

      const [dadosEmpresa, dadosIA, dadosNotificacoes, dadosIntegracoes] =
        await Promise.all(requests);

      setEmpresa(dadosEmpresa);
      setEmpresaForm({
        nome: dadosEmpresa.nome,
        telefone: dadosEmpresa.telefone ?? "",
        email: dadosEmpresa.email ?? "",
        cidade: dadosEmpresa.cidade ?? "",
        estado: dadosEmpresa.estado ?? "",
        timezone: dadosEmpresa.timezone || "America/Sao_Paulo",
      });

      if (dadosIA) {
        setIaForm({
          nome_assistente: dadosIA.nome_assistente,
          mensagem_boas_vindas: dadosIA.mensagem_boas_vindas ?? "",
          prompt: dadosIA.prompt ?? "",
          temperatura: String(dadosIA.temperatura),
        });
      }

      setNotificacoes(dadosNotificacoes);
      setIntegracoes(dadosIntegracoes ?? []);
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível carregar as configurações.");
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    void carregar();
  }, []);

  useEffect(() => {
    if (!sucesso) return;

    const timer = window.setTimeout(() => {
      setSucesso("");
    }, 4000);

    return () => window.clearTimeout(timer);
  }, [sucesso]);


  useEffect(() => {
    if (!erroTemporario) return;

    const timer = window.setTimeout(() => {
      setErroTemporario("");
    }, 4000);

    return () => window.clearTimeout(timer);
  }, [erroTemporario]);

  function solicitarConfirmacaoEmpresa(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    setErro("");
    setConfirmarDadosEmpresa(true);
  }

  function fecharConfirmacaoEmpresa() {
    if (salvando) return;

    setConfirmarDadosEmpresa(false);
    setErro("");
  }

  async function confirmarSalvarEmpresa() {
    setSalvando(true);
    setErro("");

    try {
      const atualizada = await apiRequest<Empresa>("/empresa", {
        method: "PATCH",
        body: JSON.stringify({
          nome: empresaForm.nome.trim(),
          telefone: normalizeNullable(empresaForm.telefone),
          email: normalizeNullable(empresaForm.email),
          cidade: normalizeNullable(empresaForm.cidade),
          estado: normalizeNullable(empresaForm.estado.toUpperCase()),
          timezone: empresaForm.timezone,
        }),
      });
      setEmpresa(atualizada);
      setConfirmarDadosEmpresa(false);
      setSucesso("Dados da empresa atualizados com sucesso.");
      await atualizarUsuario();
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível salvar os dados da empresa.",
      );
    } finally {
      setSalvando(false);
    }
  }

  async function alterarLogo(event: ChangeEvent<HTMLInputElement>) {
    const arquivo = event.target.files?.[0];
    event.target.value = "";

    if (!arquivo) return;

    const formatosPermitidos = ["image/png", "image/jpeg", "image/webp"];
    if (!formatosPermitidos.includes(arquivo.type)) {
      setErro("Escolha uma imagem PNG, JPG ou WebP.");
      return;
    }

    if (arquivo.size > 2 * 1024 * 1024) {
      setErro("A imagem deve ter no máximo 2 MB.");
      return;
    }

    setSalvandoLogo(true);
    setErro("");

    try {
      const formData = new FormData();
      formData.append("logo", arquivo);

      const atualizada = await apiRequest<Empresa>("/empresa/logo", {
        method: "POST",
        body: formData,
      });

      setEmpresa(atualizada);
      setSucesso("Logo da empresa atualizado com sucesso.");
      await atualizarUsuario();
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível atualizar o logo da empresa.",
      );
    } finally {
      setSalvandoLogo(false);
    }
  }

  function solicitarRemocaoLogo() {
    setErro("");
    setConfirmarRemocaoLogo(true);
  }

  function fecharConfirmacaoRemocaoLogo() {
    if (salvandoLogo) return;

    setConfirmarRemocaoLogo(false);
    setErro("");
  }

  async function removerLogo() {
    setSalvandoLogo(true);
    setErro("");

    try {
      const atualizada = await apiRequest<Empresa>("/empresa/logo", {
        method: "DELETE",
      });
      setEmpresa(atualizada);
      setConfirmarRemocaoLogo(false);
      setSucesso("Logo da empresa removido com sucesso.");
      await atualizarUsuario();
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível remover o logo da empresa.",
      );
    } finally {
      setSalvandoLogo(false);
    }
  }

  async function salvarIA(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSalvando(true);
    setErro("");
    try {
      await apiRequest<ConfigIA>("/configuracoes/ia", {
        method: "PUT",
        body: JSON.stringify({
          nome_assistente: iaForm.nome_assistente.trim(),
          mensagem_boas_vindas: normalizeNullable(iaForm.mensagem_boas_vindas),
          prompt: normalizeNullable(iaForm.prompt),
          temperatura: Number(iaForm.temperatura),
        }),
      });
      setSucesso("Configuração da IA salva.");
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível salvar a IA.");
    } finally {
      setSalvando(false);
    }
  }

  async function marcarLida(item: Notificacao) {
    try {
      const atualizada = await apiRequest<Notificacao>(
        `/notificacoes/${item.id}/lida`,
        { method: "PATCH" },
      );
      setNotificacoes((atuais) =>
        atuais.map((notificacao) =>
          notificacao.id === atualizada.id ? atualizada : notificacao,
        ),
      );
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível marcar a notificação.");
    }
  }

  async function marcarTodas() {
    try {
      const pendentes = notificacoes.filter((item) => !item.lida);
      await Promise.all(
        pendentes.map((item) =>
          apiRequest<Notificacao>(`/notificacoes/${item.id}/lida`, {
            method: "PATCH",
          }),
        ),
      );
      setNotificacoes((atuais) =>
        atuais.map((item) => ({ ...item, lida: true })),
      );
      setSucesso("Notificações marcadas como lidas.");
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível marcar as notificações.");
    }
  }

  function solicitarAlteracaoSenha(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro("");
    setErroTemporario("");

    if (senhaForm.nova_senha !== senhaForm.confirmar_senha) {
      setErroTemporario("As senhas não coincidem.");
      return;
    }

    if (senhaForm.nova_senha.length < 8) {
      setErroTemporario("A nova senha precisa ter pelo menos 8 caracteres.");
      return;
    }

    setConfirmarAlteracaoSenha(true);
  }

  function fecharConfirmacaoAlteracaoSenha() {
    if (salvando) return;

    setConfirmarAlteracaoSenha(false);
    setErro("");
  }

  async function confirmarAlterarSenha() {
    setSalvando(true);
    setErro("");

    try {
      await apiRequest<{ mensagem: string }>("/auth/alterar-senha", {
        method: "POST",
        body: JSON.stringify({
          senha_atual: senhaForm.senha_atual,
          nova_senha: senhaForm.nova_senha,
        }),
      });

      setSenhaForm({
        senha_atual: "",
        nova_senha: "",
        confirmar_senha: "",
      });
      setMostrarNovaSenha(false);
      setMostrarConfirmacaoNovaSenha(false);
      setConfirmarAlteracaoSenha(false);
      setSucesso("Senha atualizada com sucesso.");
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível alterar a senha.",
      );
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Preferências"
        title="Configurações"
        description="Gerencie a empresa, a IA, as integrações e a segurança."
      />

      {sucesso && (
        <div className="app-toast-region" aria-live="polite" aria-atomic="true">
          <div className="app-toast app-toast-success" role="status">
            <span className="app-toast-icon">
              <Icon name="check" size={18} />
            </span>
            <div className="app-toast-copy">
              <strong>Sucesso</strong>
              <span>{sucesso}</span>
            </div>
            <button
              className="app-toast-close"
              type="button"
              onClick={() => setSucesso("")}
              aria-label="Fechar notificação"
            >
              <Icon name="close" size={17} />
            </button>
          </div>
        </div>
      )}

      {erroTemporario && (
        <div className="app-toast-region" aria-live="assertive" aria-atomic="true">
          <div className="app-toast app-toast-error" role="alert">
            <span className="app-toast-icon app-toast-icon-error">
              <Icon name="close" size={18} />
            </span>
            <div className="app-toast-copy">
              <strong>Verifique os dados</strong>
              <span>{erroTemporario}</span>
            </div>
            <button
              className="app-toast-close"
              type="button"
              onClick={() => setErroTemporario("")}
              aria-label="Fechar notificação"
            >
              <Icon name="close" size={17} />
            </button>
          </div>
        </div>
      )}

      {erro &&
        !confirmarDadosEmpresa &&
        !confirmarRemocaoLogo &&
        !confirmarAlteracaoSenha && <Alert>{erro}</Alert>}

      <div className="tabs">
        <button
          className={aba === "empresa" ? "tab-active" : ""}
          onClick={() => setAba("empresa")}
        >
          Empresa
        </button>
        <button
          className={aba === "ia" ? "tab-active" : ""}
          onClick={() => setAba("ia")}
        >
          Inteligência artificial
        </button>
        <button
          className={aba === "notificacoes" ? "tab-active" : ""}
          onClick={() => setAba("notificacoes")}
        >
          Notificações
        </button>
        <button
          className={aba === "seguranca" ? "tab-active" : ""}
          onClick={() => setAba("seguranca")}
        >
          Segurança
        </button>
      </div>

      {carregando ? (
        <LoadingState label="Carregando configurações..." />
      ) : aba === "empresa" ? (
        <div className="settings-grid">
          <section className="content-card">
            <div className="card-heading">
              <div>
                <span>Dados gerais</span>
                <h2>Informações da empresa</h2>
              </div>
              <Icon name="building" size={24} />
            </div>

            <form onSubmit={solicitarConfirmacaoEmpresa}>
              <div className="form-grid form-grid-2">
                <div className="company-logo-editor field-span-2">
                  <div className="company-logo-preview">
                    {empresa?.logo ? (
                      <img
                        src={resolverLogoUrl(empresa.logo)}
                        alt={`Logo da empresa ${empresa.nome}`}
                      />
                    ) : (
                      <span>{empresa?.nome.charAt(0).toUpperCase() ?? "F"}</span>
                    )}
                  </div>

                  <div className="company-logo-editor-copy">
                    <strong>Logo da empresa</strong>
                    <p>
                      Use uma imagem quadrada em PNG, JPG ou WebP, com até 2 MB.
                    </p>
                    {podeEditar && (
                      <div className="company-logo-actions">
                        <input
                          ref={inputLogoRef}
                          className="company-logo-file-input"
                          type="file"
                          accept="image/png,image/jpeg,image/webp"
                          onChange={alterarLogo}
                        />
                        <button
                          className="button button-secondary button-small"
                          type="button"
                          onClick={() => inputLogoRef.current?.click()}
                          disabled={salvandoLogo}
                        >
                          <Icon name="edit" size={16} />
                          {salvandoLogo ? "Processando..." : "Alterar logo"}
                        </button>
                        {empresa?.logo && (
                          <button
                            className="button button-danger button-small"
                            type="button"
                            onClick={solicitarRemocaoLogo}
                            disabled={salvandoLogo}
                          >
                            <Icon name="trash" size={16} />
                            Remover
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                <label className="field field-span-2">
                  Nome da empresa
                  <input
                    value={empresaForm.nome}
                    onChange={(event) =>
                      setEmpresaForm({ ...empresaForm, nome: event.target.value })
                    }
                    disabled={!podeEditar}
                    required
                  />
                </label>
                <label className="field">
                  Telefone
                  <input
                    value={empresaForm.telefone}
                    onChange={(event) =>
                      setEmpresaForm({
                        ...empresaForm,
                        telefone: event.target.value,
                      })
                    }
                    disabled={!podeEditar}
                  />
                </label>
                <label className="field">
                  E-mail
                  <input
                    type="email"
                    value={empresaForm.email}
                    onChange={(event) =>
                      setEmpresaForm({ ...empresaForm, email: event.target.value })
                    }
                    disabled={!podeEditar}
                  />
                </label>
                <label className="field">
                  Cidade
                  <input
                    value={empresaForm.cidade}
                    onChange={(event) =>
                      setEmpresaForm({ ...empresaForm, cidade: event.target.value })
                    }
                    disabled={!podeEditar}
                  />
                </label>
                <label className="field">
                  Estado
                  <input
                    maxLength={2}
                    value={empresaForm.estado}
                    onChange={(event) =>
                      setEmpresaForm({
                        ...empresaForm,
                        estado: event.target.value.toUpperCase(),
                      })
                    }
                    disabled={!podeEditar}
                  />
                </label>
                <label className="field field-span-2">
                  Fuso horário
                  <select
                    value={empresaForm.timezone}
                    onChange={(event) =>
                      setEmpresaForm({
                        ...empresaForm,
                        timezone: event.target.value,
                      })
                    }
                    disabled={!podeEditar}
                    required
                  >
                    {fusosBrasil.map((fuso) => (
                      <option key={fuso.value} value={fuso.value}>
                        {fuso.label}
                      </option>
                    ))}
                  </select>
                  <small className="field-help">
                    Usado para registrar corretamente agendamentos, mensagens,
                    bloqueios e notificações.
                  </small>
                </label>
              </div>

              {podeEditar && (
                <div className="form-footer">
                  <button
                    className="button button-primary"
                    type="submit"
                    disabled={salvando}
                  >
                    {salvando ? "Salvando..." : "Salvar dados"}
                  </button>
                </div>
              )}
            </form>
          </section>

          <aside className="content-card company-summary">
            <div className="company-logo-large">
              {empresa?.logo ? (
                <img
                  src={resolverLogoUrl(empresa.logo)}
                  alt={`Logo da empresa ${empresa.nome}`}
                />
              ) : (
                empresa?.nome.charAt(0).toUpperCase() ?? "F"
              )}
            </div>
            <h2>{empresa?.nome}</h2>
            <p>CNPJ {empresa?.cnpj}</p>
            <StatusBadge value={empresa?.ativo ? "ATIVO" : "INATIVO"} />
            <dl className="entity-details">
              <div>
                <dt>Empresa ID</dt>
                <dd>{empresa?.id}</dd>
              </div>
              <div>
                <dt>Plano ID</dt>
                <dd>{empresa?.plano_id ?? "Sem plano"}</dd>
              </div>
              <div>
                <dt>Atualizado em</dt>
                <dd>{formatDateTime(empresa?.updated_at)}</dd>
              </div>
            </dl>
          </aside>
        </div>
      ) : aba === "ia" ? (
        <div className="settings-grid">
          <section className="content-card">
            <div className="card-heading">
              <div>
                <span>Assistente virtual</span>
                <h2>Personalidade e atendimento</h2>
              </div>
              <Icon name="bot" size={26} />
            </div>

            <form onSubmit={salvarIA}>
              <div className="form-grid">
                <label className="field">
                  Nome do assistente
                  <input
                    value={iaForm.nome_assistente}
                    onChange={(event) =>
                      setIaForm({
                        ...iaForm,
                        nome_assistente: event.target.value,
                      })
                    }
                    disabled={!podeEditar}
                    required
                  />
                </label>
                <label className="field">
                  Mensagem de boas-vindas
                  <textarea
                    rows={3}
                    value={iaForm.mensagem_boas_vindas}
                    onChange={(event) =>
                      setIaForm({
                        ...iaForm,
                        mensagem_boas_vindas: event.target.value,
                      })
                    }
                    disabled={!podeEditar}
                  />
                </label>
                <label className="field">
                  Instruções da IA
                  <textarea
                    rows={8}
                    value={iaForm.prompt}
                    onChange={(event) =>
                      setIaForm({ ...iaForm, prompt: event.target.value })
                    }
                    placeholder="Explique como o assistente deve conversar, quais serviços oferecer e quando transferir para um atendente."
                    disabled={!podeEditar}
                  />
                </label>
                <label className="field">
                  Criatividade: {Number(iaForm.temperatura).toFixed(1)}
                  <input
                    type="range"
                    min="0"
                    max="2"
                    step="0.1"
                    value={iaForm.temperatura}
                    onChange={(event) =>
                      setIaForm({
                        ...iaForm,
                        temperatura: event.target.value,
                      })
                    }
                    disabled={!podeEditar}
                  />
                </label>
              </div>

              {podeEditar && (
                <div className="form-footer">
                  <button
                    className="button button-primary"
                    type="submit"
                    disabled={salvando}
                  >
                    {salvando ? "Salvando..." : "Salvar configuração"}
                  </button>
                </div>
              )}
            </form>
          </section>

          <aside className="content-card integration-card">
            <div className="card-heading">
              <div>
                <span>Integrações</span>
                <h2>Canais conectados</h2>
              </div>
            </div>
            {integracoes.length === 0 ? (
              <div className="compact-empty">
                Nenhuma integração configurada. WhatsApp, Instagram e IA serão
                conectados na etapa de integração real.
              </div>
            ) : (
              <div className="integration-list">
                {integracoes.map((item) => (
                  <div key={item.id}>
                    <span className="integration-icon">
                      <Icon name="chat" size={18} />
                    </span>
                    <div>
                      <strong>{item.nome ?? item.tipo}</strong>
                      <small>{item.identificador ?? "Sem identificador"}</small>
                    </div>
                    <StatusBadge value={item.ativo ? "ATIVO" : "INATIVO"} />
                  </div>
                ))}
              </div>
            )}
            <Alert type="info">
              A tela já está preparada. A conexão real será feita após a
              publicação segura do backend.
            </Alert>
          </aside>
        </div>
      ) : aba === "notificacoes" ? (
        <section className="content-card">
          <div className="card-heading">
            <div>
              <span>Central de atenção</span>
              <h2>Notificações</h2>
            </div>
            <button
              className="button button-secondary"
              type="button"
              onClick={() => void marcarTodas()}
              disabled={!notificacoes.some((item) => !item.lida)}
            >
              <Icon name="check" size={17} />
              Marcar todas como lidas
            </button>
          </div>

          {notificacoes.length === 0 ? (
            <div className="compact-empty">Nenhuma notificação cadastrada.</div>
          ) : (
            <div className="notification-list">
              {notificacoes.map((item) => (
                <article
                  className={`notification-item ${
                    item.lida ? "notification-read" : ""
                  }`}
                  key={item.id}
                >
                  <span className="notification-icon">
                    <Icon name="bell" size={18} />
                  </span>
                  <div>
                    <strong>{item.titulo}</strong>
                    <p>{item.mensagem}</p>
                    <small>{formatDateTime(item.created_at)}</small>
                  </div>
                  {!item.lida && (
                    <button
                      className="button button-small button-secondary"
                      type="button"
                      onClick={() => void marcarLida(item)}
                    >
                      Marcar como lida
                    </button>
                  )}
                </article>
              ))}
            </div>
          )}
        </section>
      ) : (
        <div className="settings-grid">
          <section className="content-card">
            <div className="card-heading">
              <div>
                <span>Conta</span>
                <h2>Alterar senha</h2>
              </div>
              <Icon name="lock" size={24} />
            </div>
            <form onSubmit={solicitarAlteracaoSenha}>
              <div className="form-grid">
                <label className="field">
                  Senha atual
                  <input
                    type="password"
                    value={senhaForm.senha_atual}
                    onChange={(event) =>
                      setSenhaForm({
                        ...senhaForm,
                        senha_atual: event.target.value,
                      })
                    }
                    required
                  />
                </label>
                <label className="field">
                  Nova senha
                  <div className="password-field">
                    <input
                      type={mostrarNovaSenha ? "text" : "password"}
                      minLength={8}
                      value={senhaForm.nova_senha}
                      onChange={(event) =>
                        setSenhaForm({
                          ...senhaForm,
                          nova_senha: event.target.value,
                        })
                      }
                      required
                    />
                    <button
                      className="password-toggle"
                      type="button"
                      onClick={() => setMostrarNovaSenha((atual) => !atual)}
                      aria-label={
                        mostrarNovaSenha ? "Ocultar nova senha" : "Mostrar nova senha"
                      }
                      title={
                        mostrarNovaSenha ? "Ocultar nova senha" : "Mostrar nova senha"
                      }
                    >
                      <Icon name="eye" size={18} />
                    </button>
                  </div>
                </label>
                <label className="field">
                  Confirmar nova senha
                  <div className="password-field">
                    <input
                      type={mostrarConfirmacaoNovaSenha ? "text" : "password"}
                      minLength={8}
                      value={senhaForm.confirmar_senha}
                      onChange={(event) =>
                        setSenhaForm({
                          ...senhaForm,
                          confirmar_senha: event.target.value,
                        })
                      }
                      required
                    />
                    <button
                      className="password-toggle"
                      type="button"
                      onClick={() =>
                        setMostrarConfirmacaoNovaSenha((atual) => !atual)
                      }
                      aria-label={
                        mostrarConfirmacaoNovaSenha
                          ? "Ocultar confirmação da senha"
                          : "Mostrar confirmação da senha"
                      }
                      title={
                        mostrarConfirmacaoNovaSenha
                          ? "Ocultar confirmação da senha"
                          : "Mostrar confirmação da senha"
                      }
                    >
                      <Icon name="eye" size={18} />
                    </button>
                  </div>
                </label>
              </div>
              <div className="form-footer">
                <button
                  className="button button-primary"
                  type="submit"
                  disabled={salvando}
                >
                  {salvando ? "Alterando..." : "Alterar senha"}
                </button>
              </div>
            </form>
          </section>

          <aside className="content-card security-info">
            <span className="security-icon">
              <Icon name="lock" size={28} />
            </span>
            <h2>Sessão protegida</h2>
            <p>
              O acesso ao sistema utiliza token JWT e todas as rotas privadas
              exigem autenticação.
            </p>
            <dl className="entity-details">
              <div>
                <dt>Usuário</dt>
                <dd>{usuario.nome}</dd>
              </div>
              <div>
                <dt>Cargo</dt>
                <dd>{usuario.cargo}</dd>
              </div>
              <div>
                <dt>Empresa ID</dt>
                <dd>{usuario.empresa_id}</dd>
              </div>
            </dl>
          </aside>
        </div>
      )}

      <Modal
        open={confirmarAlteracaoSenha}
        title="Alterar senha"
        subtitle="Confirme a alteração antes de continuar."
        onClose={fecharConfirmacaoAlteracaoSenha}
        size="small"
      >
        <div className="confirmation-dialog">
          <span className="confirmation-icon confirmation-icon-success">
            <Icon name="lock" size={24} />
          </span>

          <div className="confirmation-copy">
            <strong>Confirmar alteração da senha?</strong>
            <p>
              Sua senha atual será substituída pela nova senha informada.
              Utilize a nova senha no próximo acesso ao sistema.
            </p>
          </div>

          {erro && <Alert>{erro}</Alert>}

          <div className="modal-actions confirmation-actions">
            <button
              className="button button-secondary"
              type="button"
              onClick={fecharConfirmacaoAlteracaoSenha}
              disabled={salvando}
            >
              Cancelar
            </button>
            <button
              className="button button-primary"
              type="button"
              onClick={() => void confirmarAlterarSenha()}
              disabled={salvando}
            >
              {salvando ? "Alterando..." : "Alterar senha"}
            </button>
          </div>
        </div>
      </Modal>

      <Modal
        open={confirmarDadosEmpresa}
        title="Salvar dados da empresa"
        subtitle="Confirme as alterações antes de continuar."
        onClose={fecharConfirmacaoEmpresa}
        size="small"
      >
        <div className="confirmation-dialog">
          <span className="confirmation-icon confirmation-icon-success">
            <Icon name="check" size={24} />
          </span>

          <div className="confirmation-copy">
            <strong>Salvar as alterações da empresa?</strong>
            <p>
              Nome, contato, localização e fuso horário serão atualizados com
              os valores preenchidos nesta tela.
            </p>
          </div>

          {erro && <Alert>{erro}</Alert>}

          <div className="modal-actions confirmation-actions">
            <button
              className="button button-secondary"
              type="button"
              onClick={fecharConfirmacaoEmpresa}
              disabled={salvando}
            >
              Cancelar
            </button>
            <button
              className="button button-primary"
              type="button"
              onClick={() => void confirmarSalvarEmpresa()}
              disabled={salvando}
            >
              {salvando ? "Salvando..." : "Salvar dados"}
            </button>
          </div>
        </div>
      </Modal>

      <Modal
        open={confirmarRemocaoLogo}
        title="Remover logo"
        subtitle="Confirme a remoção antes de continuar."
        onClose={fecharConfirmacaoRemocaoLogo}
        size="small"
      >
        <div className="confirmation-dialog">
          <span className="confirmation-icon confirmation-icon-danger">
            <Icon name="trash" size={24} />
          </span>

          <div className="confirmation-copy">
            <strong>Remover o logo da empresa?</strong>
            <p>
              A imagem atual será removida e o sistema voltará a mostrar a
              inicial do nome da empresa.
            </p>
          </div>

          {erro && <Alert>{erro}</Alert>}

          <div className="modal-actions confirmation-actions">
            <button
              className="button button-secondary"
              type="button"
              onClick={fecharConfirmacaoRemocaoLogo}
              disabled={salvandoLogo}
            >
              Cancelar
            </button>
            <button
              className="button button-danger"
              type="button"
              onClick={() => void removerLogo()}
              disabled={salvandoLogo}
            >
              {salvandoLogo ? "Removendo..." : "Remover logo"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
