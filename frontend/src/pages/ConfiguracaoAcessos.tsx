import { useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router";
import { Icon } from "../components/Icon";
import { Alert, LoadingState, PageHeader } from "../components/UI";
import { apiRequest } from "../services/api";
import { showAppToast } from "../services/feedback";
import type { AppOutletContext } from "../types";
import type {
  AccessConfiguration,
  CompanyModule,
  ModuleCode,
  UserModulePermissions,
} from "../types/accessControl";

type Tab = "modules" | "permissions";
type PermissionChoice = "DEFAULT" | "ALLOW" | "DENY";
type PermissionLevel = "view" | "manage";

const roleLabels = {
  ADMIN: "Administrador",
  GERENTE: "Gerente",
  FUNCIONARIO: "Funcionário",
} as const;

const moduleIcons: Partial<Record<ModuleCode, "finance" | "team" | "calendar" | "chat" | "users" | "car" | "services" | "dashboard">> = {
  AGENDA: "calendar",
  CHAT_INTERNO: "chat",
  CONVERSAS: "chat",
  CLIENTES: "users",
  VEICULOS: "car",
  SERVICOS: "services",
  FINANCEIRO: "finance",
  RELATORIOS: "dashboard",
  EQUIPE: "team",
};

const viewOnlyModules = new Set<ModuleCode>(["RELATORIOS"]);

const viewDescriptions: Partial<Record<ModuleCode, string>> = {
  FINANCEIRO:
    "Mostra somente os atendimentos do próprio profissional e permite receber as próprias pendências.",
  EQUIPE: "Mostra somente a lista de usuários, sem jornadas e bloqueios.",
  RELATORIOS: "Permite consultar os indicadores e gráficos disponíveis.",
};

const managementDescriptions: Partial<Record<ModuleCode, string>> = {
  CHAT_INTERNO: "Permite criar novos grupos no chat interno.",
  CONVERSAS: "Permite iniciar uma nova conversa com cliente.",
  CLIENTES: "Permite cadastrar, editar e alterar a situação dos clientes.",
  VEICULOS: "Permite cadastrar, editar e excluir veículos.",
  SERVICOS: "Permite cadastrar, editar, desativar e reativar serviços.",
  FINANCEIRO:
    "Mostra todos os atendimentos, permite receber pendências de outros profissionais, ajustar e estornar.",
  EQUIPE: "Libera a gestão dos usuários, jornadas e bloqueios da agenda.",
};

export function ConfiguracaoAcessos() {
  const { usuario, atualizarUsuario } = useOutletContext<AppOutletContext>();
  const [tab, setTab] = useState<Tab>("modules");
  const [configuration, setConfiguration] = useState<AccessConfiguration | null>(null);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState("");
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await apiRequest<AccessConfiguration>("/acessos/configuracao");
      setConfiguration(data);
      setSelectedUserId((current) =>
        current && data.users.some((item) => item.user_id === current)
          ? current
          : data.users[0]?.user_id ?? null,
      );
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Não foi possível carregar módulos e permissões.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const selectedUser = useMemo(
    () =>
      configuration?.users.find((item) => item.user_id === selectedUserId) ?? null,
    [configuration, selectedUserId],
  );

  async function toggleModule(module: CompanyModule) {
    const key = `module-${module.code}`;
    setSavingKey(key);
    setError("");
    try {
      const updated = await apiRequest<CompanyModule>(
        `/acessos/modulos/${module.code}`,
        {
          method: "PATCH",
          body: JSON.stringify({ enabled: !module.enabled }),
        },
      );
      await Promise.all([load(), atualizarUsuario()]);
      showAppToast(
        updated.enabled
          ? `${updated.name} ativado para a empresa.`
          : `${updated.name} removido do menu da empresa.`,
      );
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Não foi possível alterar o módulo.",
      );
    } finally {
      setSavingKey("");
    }
  }

  function permissionChoice(
    user: UserModulePermissions,
    module: ModuleCode,
    level: PermissionLevel,
  ): PermissionChoice {
    const overrides =
      level === "view" ? user.overrides : user.management_overrides;
    if (!(module in overrides)) return "DEFAULT";
    return overrides[module] ? "ALLOW" : "DENY";
  }

  async function updatePermission(
    user: UserModulePermissions,
    module: CompanyModule,
    level: PermissionLevel,
    choice: PermissionChoice,
  ) {
    if (level === "manage" && viewOnlyModules.has(module.code)) return;

    const key = `permission-${user.user_id}-${module.code}-${level}`;
    setSavingKey(key);
    setError("");
    const value = choice === "DEFAULT" ? null : choice === "ALLOW";

    try {
      const updated = await apiRequest<UserModulePermissions>(
        `/acessos/usuarios/${user.user_id}/modulos/${module.code}`,
        {
          method: "PATCH",
          body: JSON.stringify(
            level === "view"
              ? { view_allowed: value }
              : { manage_allowed: value },
          ),
        },
      );
      setConfiguration((current) =>
        current
          ? {
              ...current,
              users: current.users.map((item) =>
                item.user_id === updated.user_id ? updated : item,
              ),
            }
          : current,
      );
      if (user.user_id === usuario.id) {
        await atualizarUsuario();
      }
      showAppToast(
        `${level === "view" ? "Visualização" : "Gerenciamento"} de ${module.name} atualizado para ${user.name}.`,
      );
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Não foi possível alterar a permissão.",
      );
    } finally {
      setSavingKey("");
    }
  }

  function PermissionSelector({
    user,
    module,
    level,
  }: {
    user: UserModulePermissions;
    module: CompanyModule;
    level: PermissionLevel;
  }) {
    const choice = permissionChoice(user, module.code, level);
    const effective =
      level === "view"
        ? user.permissions[module.code]
        : user.management_permissions[module.code];
    const key = `permission-${user.user_id}-${module.code}-${level}`;
    const description =
      level === "view"
        ? viewDescriptions[module.code] ??
          "Permite abrir a área e consultar suas informações."
        : managementDescriptions[module.code] ??
          "Permite executar ações administrativas e alterações do módulo.";

    return (
      <section className="access-level-control">
        <div className="access-level-copy">
          <strong>{level === "view" ? "Visualizar" : "Gerenciar"}</strong>
          <small>{description}</small>
        </div>
        <div
          className="access-choice-group"
          role="group"
          aria-label={`${level === "view" ? "Visualização" : "Gerenciamento"} de ${module.name}`}
        >
          {(
            [
              ["DEFAULT", "Padrão"],
              ["ALLOW", "Liberar"],
              ["DENY", "Bloquear"],
            ] as const
          ).map(([value, label]) => (
            <button
              className={`${choice === value ? "active" : ""} choice-${value.toLowerCase()}`}
              type="button"
              key={value}
              onClick={() => void updatePermission(user, module, level, value)}
              disabled={!module.enabled || savingKey === key}
              aria-pressed={choice === value}
            >
              {label}
            </button>
          ))}
        </div>
        <span className={`access-effective-state ${effective ? "allowed" : "blocked"}`}>
          <Icon name={effective ? "check" : "lock"} size={13} />
          {effective ? "Atualmente liberado" : "Atualmente bloqueado"}
        </span>
      </section>
    );
  }

  return (
    <div className="page access-settings-page">
      <PageHeader
        eyebrow="Personalização da empresa"
        title="Módulos e permissões"
        description="Escolha quais áreas aparecem no sistema e defina quem pode apenas visualizar ou também gerenciar."
      />

      {error && <Alert>{error}</Alert>}

      <div className="tabs access-settings-tabs" role="tablist">
        <button
          className={tab === "modules" ? "tab-active" : ""}
          type="button"
          onClick={() => setTab("modules")}
        >
          Módulos
        </button>
        <button
          className={tab === "permissions" ? "tab-active" : ""}
          type="button"
          onClick={() => setTab("permissions")}
        >
          Permissões por usuário
        </button>
      </div>

      {loading || !configuration ? (
        <section className="content-card">
          <LoadingState label="Carregando acessos..." />
        </section>
      ) : tab === "modules" ? (
        <section className="content-card access-module-card">
          <div className="card-heading">
            <div>
              <span>Menu da empresa</span>
              <h2>Áreas ativas</h2>
            </div>
          </div>
          <p className="access-settings-help">
            Ao desativar um módulo, ele some do menu para todos e suas rotas ficam bloqueadas. Os dados existentes não são apagados.
          </p>
          <div className="access-module-list">
            {configuration.modules.map((module) => (
              <article key={module.code}>
                <span className="access-module-icon">
                  <Icon name={moduleIcons[module.code] ?? "settings"} size={19} />
                </span>
                <div>
                  <strong>{module.name}</strong>
                  <p>{module.description}</p>
                </div>
                <label className="access-switch">
                  <input
                    type="checkbox"
                    checked={module.enabled}
                    onChange={() => void toggleModule(module)}
                    disabled={savingKey === `module-${module.code}`}
                    aria-label={`${module.enabled ? "Desativar" : "Ativar"} ${module.name}`}
                  />
                  <span aria-hidden="true" />
                </label>
              </article>
            ))}
          </div>
        </section>
      ) : (
        <section className="content-card access-permission-card">
          <div className="access-user-selector">
            <label className="field">
              Usuário
              <select
                value={selectedUserId ?? ""}
                onChange={(event) => setSelectedUserId(Number(event.target.value))}
              >
                {configuration.users.map((user) => (
                  <option key={user.user_id} value={user.user_id}>
                    {user.name} — {roleLabels[user.role]}
                  </option>
                ))}
              </select>
            </label>
            {selectedUser && (
              <div className="access-selected-user">
                <span>{selectedUser.name.charAt(0).toUpperCase()}</span>
                <div>
                  <strong>{selectedUser.name}</strong>
                  <small>
                    {selectedUser.email} · {roleLabels[selectedUser.role]}
                  </small>
                </div>
              </div>
            )}
          </div>

          <p className="access-settings-help">
            O padrão do cargo continua sendo a base. Use as liberações individuais para pessoas de confiança. A permissão Gerenciar só tem efeito quando Visualizar também estiver liberado.
          </p>

          {selectedUser && (
            <div className="access-permission-list access-permission-level-list">
              {configuration.modules.map((module) => {
                const somenteVisualizacao = viewOnlyModules.has(module.code);
                return (
                  <article
                    key={module.code}
                    className={`access-permission-module ${
                      !module.enabled ? "disabled" : ""
                    }`}
                  >
                    <header>
                      <span className="access-module-icon">
                        <Icon
                          name={moduleIcons[module.code] ?? "settings"}
                          size={18}
                        />
                      </span>
                      <div>
                        <strong>{module.name}</strong>
                        <small>
                          {!module.enabled
                            ? "Módulo desativado para a empresa"
                            : somenteVisualizacao
                              ? "Este módulo possui somente visualização."
                              : module.description}
                        </small>
                      </div>
                    </header>
                    <div
                      className={`access-level-grid ${
                        somenteVisualizacao ? "access-level-grid-single" : ""
                      }`}
                    >
                      <PermissionSelector
                        user={selectedUser}
                        module={module}
                        level="view"
                      />
                      {!somenteVisualizacao && (
                        <PermissionSelector
                          user={selectedUser}
                          module={module}
                          level="manage"
                        />
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
