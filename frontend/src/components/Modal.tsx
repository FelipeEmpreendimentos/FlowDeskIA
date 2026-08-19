import {
  cloneElement,
  isValidElement,
  useEffect,
  type ReactElement,
  type ReactNode,
} from "react";
import { Icon } from "./Icon";

interface ModalProps {
  open: boolean;
  title: string;
  subtitle?: string;
  children: ReactNode;
  onClose: () => void;
  size?: "small" | "medium" | "large";
}

export function Modal({
  open,
  title,
  subtitle,
  children,
  onClose,
  size = "medium",
}: ModalProps) {
  useEffect(() => {
    if (!open) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }

    window.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose]);

  if (!open) return null;

  // Alguns navegadores bloqueiam silenciosamente o submit de inputs de horário
  // quando consideram um campo nativo inválido. Nas jornadas preferimos deixar
  // o submit chegar ao handler e usar as validações do FlowDeskIA/backend, que
  // retornam uma mensagem clara para o usuário.
  const formularioJornada = title.toLocaleLowerCase("pt-BR").includes("jornada");
  const conteudo =
    formularioJornada && isValidElement(children) && children.type === "form"
      ? cloneElement(
          children as ReactElement<{ noValidate?: boolean }>,
          { noValidate: true },
        )
      : children;

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <section
        className={`modal modal-${size}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="modal-header">
          <div>
            <h2 id="modal-title">{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Fechar">
            <Icon name="close" />
          </button>
        </header>
        <div className="modal-body">{conteudo}</div>
      </section>
    </div>
  );
}
