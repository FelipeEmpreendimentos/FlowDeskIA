const SUPER_ADMIN_TOKEN_KEY = "flowdesk_super_admin_token";

export function getSuperAdminToken(): string | null {
  return localStorage.getItem(SUPER_ADMIN_TOKEN_KEY);
}

export function saveSuperAdminSession(token: string): void {
  localStorage.setItem(SUPER_ADMIN_TOKEN_KEY, token);
}

export function clearSuperAdminSession(): void {
  localStorage.removeItem(SUPER_ADMIN_TOKEN_KEY);
}
