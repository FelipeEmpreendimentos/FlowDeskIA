import type { UsuarioLogado } from "../types";
import type { CurrentAccess } from "../types/accessControl";

const TOKEN_KEY = "flowdesk_token";
const COMPANY_KEY = "flowdesk_empresa_id";
const SESSION_CONTEXT_KEY = "flowdesk_session_context";
const API_URL = import.meta.env.PROD
  ? "/api/v1"
  : import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

export interface SessionContext {
  usuario: UsuarioLogado;
  acesso: CurrentAccess;
}

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

export function getSessionContext(): SessionContext | null {
  const raw = sessionStorage.getItem(SESSION_CONTEXT_KEY);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as SessionContext;
    if (
      !parsed?.usuario?.id ||
      !parsed?.usuario?.empresa_id ||
      !parsed?.acesso?.modules ||
      !parsed?.acesso?.management
    ) {
      sessionStorage.removeItem(SESSION_CONTEXT_KEY);
      return null;
    }
    return parsed;
  } catch {
    sessionStorage.removeItem(SESSION_CONTEXT_KEY);
    return null;
  }
}

export function saveSessionContext(
  usuario: UsuarioLogado,
  acesso: CurrentAccess,
): void {
  sessionStorage.setItem(
    SESSION_CONTEXT_KEY,
    JSON.stringify({ usuario, acesso } satisfies SessionContext),
  );
}

export function clearSessionContext(): void {
  sessionStorage.removeItem(SESSION_CONTEXT_KEY);
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
  const token = getToken();

  if (token) {
    void fetch(`${API_URL}/atendimento-equipe/me`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ status: "OFFLINE" }),
      keepalive: true,
    }).catch(() => {
      // O heartbeat também derruba o status efetivo se o navegador desaparecer.
    });
  }

  sessionStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(TOKEN_KEY);
  clearSessionContext();

  if (!options.keepCompanyId) {
    localStorage.removeItem(COMPANY_KEY);
  }

  // O cookie é HttpOnly e só pode ser removido pelo backend.
  void fetch(`${API_URL}/auth/logout`, {
    method: "POST",
    credentials: "include",
    keepalive: true,
  }).catch(() => {
    // A sessão local já foi removida mesmo quando o servidor está indisponível.
  });
}
