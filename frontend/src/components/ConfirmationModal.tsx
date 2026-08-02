import { Icon, type IconName } from "./Icon";
import { Modal } from "./Modal";
import { Alert } from "./UI";

interface ConfirmationModalProps {
  open: boolean;
  title: string;
  subtitle?: string;
  heading: string;
  description: string;
  confirmLabel: string;
  onClose: () => void;
  onConfirm: () => void;
  loading?: boolean;
  error?: string;
  tone?: "danger" | "primary";
  icon?: IconName;
}

export function ConfirmationModal({
  open,
  title,
  subtitle = "Confirme esta ação antes de continuar.",
  heading,
  description,
  confirmLabel,
  onClose,
  onConfirm,
  loading = false,
  error = "",
  tone = "danger",
  icon = "lock",
}: ConfirmationModalProps) {
  return (
    <Modal
      open={open}
      title={title}
      subtitle={subtitle}
      onClose={onClose}
      size="small"
    >
      <div className="confirmation-dialog">
        <span
          className={`confirmation-icon confirmation-icon-${tone}`}
          aria-hidden="true"
        >
          <Icon name={icon} size={24} />
        </span>
        <div className="confirmation-copy">
          <strong>{heading}</strong>
          <p>{description}</p>
        </div>
        {error && <Alert>{error}</Alert>}
        <div className="modal-actions confirmation-actions">
          <button
            className="button button-secondary"
            type="button"
            onClick={onClose}
            disabled={loading}
          >
            Voltar
          </button>
          <button
            className={
              tone === "danger"
                ? "button button-danger"
                : "button button-primary"
            }
            type="button"
            onClick={onConfirm}
            disabled={loading}
          >
            {loading ? "Processando..." : confirmLabel}
          </button>
        </div>
      </div>
    </Modal>
  );
}
