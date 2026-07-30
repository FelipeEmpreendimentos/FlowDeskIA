import type { ReactNode } from "react";
import type { AppToastType } from "../services/api";
import { Icon, type IconName } from "./Icon";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <span className="page-eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon: IconName;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon name={icon} size={26} />
      </span>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function LoadingState({ label = "Carregando..." }: { label?: string }) {
  return (
    <div className="loading-state">
      <span className="spinner" />
      <span>{label}</span>
    </div>
  );
}

export function Alert({
  type = "error",
  children,
}: {
  type?: "error" | "success" | "info";
  children: ReactNode;
}) {
  return <div className={`alert alert-${type}`}>{children}</div>;
}

export function AppToast({
  type,
  title,
  message,
  onClose,
}: {
  type: AppToastType;
  title: string;
  message: string;
  onClose: () => void;
}) {
  const iconByType: Record<AppToastType, IconName> = {
    success: "check",
    error: "close",
    warning: "lock",
    info: "bell",
  };

  return (
    <div
      className="app-toast-region"
      aria-live={type === "error" || type === "warning" ? "assertive" : "polite"}
      aria-atomic="true"
    >
      <div
        className={`app-toast app-toast-${type}`}
        role={type === "error" || type === "warning" ? "alert" : "status"}
      >
        <span className={`app-toast-icon app-toast-icon-${type}`}>
          <Icon name={iconByType[type]} size={18} />
        </span>
        <div className="app-toast-copy">
          <strong>{title}</strong>
          <span>{message}</span>
        </div>
        <button
          className="app-toast-close"
          type="button"
          onClick={onClose}
          aria-label="Fechar notificação"
        >
          <Icon name="close" size={17} />
        </button>
      </div>
    </div>
  );
}

export function StatusBadge({ value }: { value: string }) {
  const key = value.toLowerCase().replaceAll("_", "-");
  const labels: Record<string, string> = {
    ATIVO: "Ativo",
    INATIVO: "Inativo",
    BLOQUEADO: "Bloqueado",
    PENDENTE: "Pendente",
    CONFIRMADO: "Confirmado",
    EM_ANDAMENTO: "Em andamento",
    FINALIZADO: "Finalizado",
    CANCELADO: "Cancelado",
    ABERTA: "Aberta",
    EM_ATENDIMENTO: "Em atendimento",
    FINALIZADA: "Finalizada",
    ADMIN: "Administrador",
    GERENTE: "Gerente",
    FUNCIONARIO: "Funcionário",
    WHATSAPP: "WhatsApp",
    INSTAGRAM: "Instagram",
    SITE: "Site",
  };

  return <span className={`status-badge status-${key}`}>{labels[value] ?? value}</span>;
}
