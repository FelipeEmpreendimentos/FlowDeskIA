const MAX_CONTACT_DIGITS = 15;

function isContactInput(target: EventTarget | null): target is HTMLInputElement {
  if (!(target instanceof HTMLInputElement)) return false;

  if (
    target.type === "tel" ||
    target.inputMode === "tel" ||
    target.inputMode === "numeric" ||
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
  input.maxLength = MAX_CONTACT_DIGITS;
  input.pattern = "[0-9]*";

  const normalized = input.value.replace(/\D/g, "").slice(0, MAX_CONTACT_DIGITS);
  if (input.value !== normalized) {
    input.value = normalized;
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
    "beforeinput",
    (event) => {
      if (!isContactInput(event.target)) return;
      const inputEvent = event as InputEvent;
      const input = event.target;

      if (!inputEvent.data || !inputEvent.inputType.startsWith("insert")) return;
      if (/\D/.test(inputEvent.data)) {
        event.preventDefault();
        return;
      }

      const start = input.selectionStart ?? input.value.length;
      const end = input.selectionEnd ?? start;
      const nextLength =
        input.value.length - (end - start) + inputEvent.data.length;
      if (nextLength > MAX_CONTACT_DIGITS) {
        event.preventDefault();
      }
    },
    true,
  );

  document.addEventListener(
    "paste",
    (event) => {
      if (!isContactInput(event.target)) return;
      const input = event.target;
      const digits = event.clipboardData
        ?.getData("text")
        .replace(/\D/g, "") ?? "";

      event.preventDefault();

      const start = input.selectionStart ?? input.value.length;
      const end = input.selectionEnd ?? start;
      const available = Math.max(
        0,
        MAX_CONTACT_DIGITS - (input.value.length - (end - start)),
      );
      input.setRangeText(digits.slice(0, available), start, end, "end");
      input.dispatchEvent(new Event("input", { bubbles: true }));
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
