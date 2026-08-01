const TOKEN_KEY = "flowdesk_token";
const COMPANY_KEY = "flowdesk_empresa_id";

export function getToken(): string | null {
  const sessionToken = sessionStorage.getItem(TOKEN_KEY);
  if (sessionToken) return sessionToken;

  // Migra automaticamente sessões antigas que ainda estavam no localStorage.
  const legacyToken = localStorage.getItem(TOKEN_KEY);
  if (legacyToken) {
    sessionStorage.setItem(TOKEN_KEY, legacyToken);
    localStorage.removeItem(TOKEN_KEY);
    return legacyToken;
  }

  return null;
}

export function getCompanyId(): string {
  return localStorage.getItem(COMPANY_KEY) ?? "2";
}

export function saveAccessToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
  localStorage.removeItem(TOKEN_KEY);
}

export function saveSession(token: string, empresaId: string): void {
  saveAccessToken(token);
  localStorage.setItem(COMPANY_KEY, empresaId);
}

export function clearSession(options: { keepCompanyId?: boolean } = {}): void {
  sessionStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(TOKEN_KEY);

  if (!options.keepCompanyId) {
    localStorage.removeItem(COMPANY_KEY);
  }
}
