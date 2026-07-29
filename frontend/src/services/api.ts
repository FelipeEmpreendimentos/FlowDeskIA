import { clearSession, getToken } from "./auth";

const API_URL =
  import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api/v1";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function buildQuery(
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

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);

  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;

  try {
    response = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      headers,
    });
  } catch {
    throw new ApiError(
      "Não foi possível conectar ao servidor. Confirme se o backend está ligado.",
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
      // Mantém a mensagem padrão quando a API não retorna JSON.
    }

    const publicAuthEndpoints = [
      "/auth/login",
      "/auth/recuperar-senha",
      "/auth/redefinir-senha",
    ];

    if (
      response.status === 401 &&
      getToken() &&
      !publicAuthEndpoints.includes(endpoint)
    ) {
      clearSession();
      window.location.assign("/login");
    }

    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
