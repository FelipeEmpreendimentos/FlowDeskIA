import type { ReactNode } from "react";
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
