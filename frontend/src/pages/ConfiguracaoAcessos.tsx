import { useEffect, useMemo, useState } from "react";
import { Icon } from "../components/Icon";
import { Alert, LoadingState, PageHeader } from "../components/UI";
import { apiRequest } from "../services/api";
import { showAppToast } from "../services/feedback";
import type {
  AccessConfiguration,
  CompanyModule,
  ModuleCode,
  UserModulePermissions,
} from "../types/accessControl";

type Tab = "modules" | "permissions";
type PermissionChoice = "DEFAULT" | "ALLOW" | "DENY";

const roleLabels = {
  ADMIN: "Administrador",
  GERENTE: "Gerente",
  FUNCIONARIO: "Funcionário",
} as const;

export function ConfiguracaoAcessos() {
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

  function updateModuleLocally(updated: CompanyModule) {
    setConfiguration((current) =>
      current
        ? {
            ...current,
            modules: current.modules.map((item) =>
              item.code === updated.code ? updated : item,
            ),
            users: current.users.map((user) => ({
              ...user,
              permissions: {
                ...user.permissions,
                [updated.code]: updated.enabled
                  ? user.overrides[updated.code] ?? user.permissions[updated.code]
                  : false,
              },
            })),
          }
        : current,
    );
  }

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
      updateModuleLocally(updated);
      await load();
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
  ): PermissionChoice {
    if (!(module in user.overrides)) return "DEFAULT";
    return user.overrides[module] ? "ALLOW" : "DENY";
  }

  async function updatePermission(
    user: UserModulePermissions,
    module: CompanyModule,
    choice: PermissionChoice,
  ) {
    const key = `permission-${user.user_id}-${module.code}`;
    setSavingKey(key);
    setError("");
    try {
      const updated = await apiRequest<UserModulePermissions>(
        `/acessos/usuarios/${user.user_id}/modulos/${module.code}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            allowed:
              choice === "DEFAULT" ? null : choice === "ALLOW",
          }),
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
      showAppToast(`Permissão de ${user.name} atualizada.`);
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

  return (
    <div className="page access-settings-page">
      <PageHeader
        eyebrow="Personalização da empresa"
        title="Módulos e permissões"
        description="Escolha quais áreas aparecem no sistema e libere acessos específicos para cada pessoa."
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
            Ao desativar um módulo, ele some do menu para todos e suas rotas ficam bloqueadas.
            Os dados existentes não são apagados.
          </p>
          <div className="access-module-list">
            {configuration.modules.map((module) => (
              <article key={module.code}>
                <span className="access-module-icon">
                  <Icon name={module.code === "FINANCEIRO" ? "finance" : "settings"} size={19} />
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
                  <small>{selectedUser.email} · {roleLabels[selectedUser.role]}</small>
                </div>
              </div>
            )}
          </div>

          <p className="access-settings-help">
            “Padrão do cargo” mantém o acesso normal. Use “Liberar” ou “Bloquear” somente
            para exceções individuais.
          </p>

          {selectedUser && (
            <div className="access-permission-list">
              {configuration.modules.map((module) => {
                const choice = permissionChoice(selectedUser, module.code);
                return (
                  <article key={module.code} className={!module.enabled ? "disabled" : ""}>
                    <div>
                      <strong>{module.name}</strong>
                      <small>
                        {!module.enabled
                          ? "Módulo desativado para a empresa"
                          : selectedUser.permissions[module.code]
                            ? "Acesso atual: liberado"
                            : "Acesso atual: bloqueado"}
                      </small>
                    </div>
                    <select
                      value={choice}
                      onChange={(event) =>
                        void updatePermission(
                          selectedUser,
                          module,
                          event.target.value as PermissionChoice,
                        )
                      }
                      disabled={
                        !module.enabled ||
                        savingKey === `permission-${selectedUser.user_id}-${module.code}`
                      }
                      aria-label={`Permissão de ${selectedUser.name} para ${module.name}`}
                    >
                      <option value="DEFAULT">Padrão do cargo</option>
                      <option value="ALLOW">Liberar</option>
                      <option value="DENY">Bloquear</option>
                    </select>
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
