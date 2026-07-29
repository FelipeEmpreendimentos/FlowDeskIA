const TOKEN_KEY = "flowdesk_token";
const COMPANY_KEY = "flowdesk_empresa_id";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getCompanyId(): string {
  return localStorage.getItem(COMPANY_KEY) ?? "2";
}

export function saveSession(token: string, empresaId: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(COMPANY_KEY, empresaId);
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(COMPANY_KEY);
}
