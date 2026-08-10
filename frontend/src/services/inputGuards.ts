const MAX_MOBILE_DIGITS = 11;
const MAX_MOBILE_FORMATTED_LENGTH = 15;

export function mobileDigits(value: string | null | undefined): string {
  return (value ?? "").replace(/\D/g, "").slice(0, MAX_MOBILE_DIGITS);
}

export function formatBrazilianMobile(value: string | null | undefined): string {
  const digits = mobileDigits(value);
  if (!digits) return "";
  if (digits.length < 3) return `(${digits}`;

  const ddd = digits.slice(0, 2);
  const numero = digits.slice(2);
  if (numero.length <= 5) return `(${ddd}) ${numero}`;

  return `(${ddd}) ${numero.slice(0, 5)}-${numero.slice(5)}`;
}

function isContactInput(target: EventTarget | null): target is HTMLInputElement {
  if (!(target instanceof HTMLInputElement)) return false;

  // A regra de celular desta rodada vale especificamente para Clientes e
  // Usuários da equipe. Outros telefones da empresa podem ter regras próprias.
  if (!target.closest(".route-clientes, .route-equipe")) return false;

  if (
    target.type === "tel" ||
    target.inputMode === "tel" ||
    target.autocomplete === "tel"
  ) {
    return true;
  }

  const label = target.closest("label");
  const text = label?.textContent?.toLocaleLowerCase("pt-BR") ?? "";
  return text.includes("telefone") || text.includes("whatsapp");
}

function normalizeContactInput(input: HTMLInputElement): void {
  input.inputMode = "numeric";
  input.maxLength = MAX_MOBILE_FORMATTED_LENGTH;

  const formatted = formatBrazilianMobile(input.value);
  if (input.value !== formatted) {
    input.value = formatted;
  }
}

export function installContactInputGuards(): void {
  document.addEventListener(
    "focusin",
    (event) => {
      if (!isContactInput(event.target)) return;
      normalizeContactInput(event.target);
    },
    true,
  );

  document.addEventListener(
    "input",
    (event) => {
      if (!isContactInput(event.target)) return;
      normalizeContactInput(event.target);
    },
    true,
  );
}
