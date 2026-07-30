import { clearSuperAdminSession, getSuperAdminToken } from "./superAdminAuth";

const API_URL =
  import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api/v1";

export class SuperAdminApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "SuperAdminApiError";
    this.status = status;
  }
}

export function superAdminBuildQuery(
  values: Record<string, string | number | boolean | null | undefined>,
): string {
  const query = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") {
      query.set(key, String(value));
    }
  });
  const serialized = query.toString();
  return serialized ? `?${serialized}` : "";
}

export async function superAdminApiRequest<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getSuperAdminToken();
  const headers = new Headers(options.headers);

  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}/super-admin${endpoint}`, {
      ...options,
      headers,
    });
  } catch {
    throw new SuperAdminApiError(
      "Não foi possível conectar ao servidor do FlowDeskIA.",
      0,
    );
  }

  if (!response.ok) {
    let message = "Não foi possível concluir a solicitação.";
    try {
      const error = (await response.json()) as {
        detail?: string | Array<{ msg?: string }>;
      };
      if (typeof error.detail === "string") {
        message = error.detail;
      } else if (Array.isArray(error.detail) && error.detail[0]?.msg) {
        message = error.detail[0].msg;
      }
    } catch {
      // Mantém a mensagem padrão.
    }

    if (response.status === 401 && token && endpoint !== "/auth/login") {
      clearSuperAdminSession();
      window.location.assign("/super-admin/login");
    }
    throw new SuperAdminApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
