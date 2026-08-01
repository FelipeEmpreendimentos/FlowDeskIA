import {
  clearSession,
  getToken,
  saveAccessToken,
} from "./auth";

const API_URL =
  import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

export const APP_TOAST_EVENT = "flowdesk:toast";

export type AppToastType = "success" | "error" | "warning" | "info";

export interface AppToastEventDetail {
  type: AppToastType;
  title: string;
  message: string;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const publicAuthEndpoints = [
  "/auth/login",
  "/auth/refresh",
  "/auth/logout",
  "/auth/recuperar-senha",
  "/auth/redefinir-senha",
];

let refreshPromise: Promise<boolean> | null = null;

function emitAppToast(detail: AppToastEventDetail): void {
  window.dispatchEvent(
    new CustomEvent<AppToastEventDetail>(APP_TOAST_EVENT, { detail }),
  );
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

async function fetchApi(
  endpoint: string,
  options: RequestInit,
  token: string | null,
): Promise<Response> {
  const headers = new Headers(options.headers);

  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  } else {
    headers.delete("Authorization");
  }

  return fetch(`${API_URL}${endpoint}`, {
    ...options,
    credentials: options.credentials ?? "include",
    headers,
  });
}

async function renovarAccessToken(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    try {
      const response = await fetch(`${API_URL}/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });

      if (!response.ok) return false;

      const data = (await response.json()) as TokenResponse;
      saveAccessToken(data.access_token);
      return true;
    } catch {
      return false;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

export async function restoreRememberedSession(): Promise<boolean> {
  if (getToken()) return true;
  return renovarAccessToken();
}

async function mensagemErro(response: Response): Promise<string> {
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

  return message;
}

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  let response: Response;

  try {
    response = await fetchApi(endpoint, options, getToken());

    const podeRenovar =
      response.status === 401 &&
      !publicAuthEndpoints.includes(endpoint);

    if (podeRenovar && (await renovarAccessToken())) {
      response = await fetchApi(endpoint, options, getToken());
    }
  } catch {
    throw new ApiError(
      "Não foi possível conectar ao servidor. Confirme se o backend está ligado.",
      0,
    );
  }

  if (!response.ok) {
    const message = await mensagemErro(response);

    if (
      response.status === 401 &&
      !publicAuthEndpoints.includes(endpoint)
    ) {
      clearSession({ keepCompanyId: true });
      window.location.assign("/login");
    }

    const shouldUsePermissionToast =
      response.status === 403 &&
      Boolean(getToken()) &&
      endpoint !== "/auth/me" &&
      !publicAuthEndpoints.includes(endpoint);

    if (shouldUsePermissionToast) {
      const isPlanRestriction = /plano|limite|recurso|franquia/i.test(message);
      emitAppToast({
        type: "warning",
        title: isPlanRestriction ? "Recurso indisponível" : "Acesso restrito",
        message,
      });

      // O aviso já foi exibido no canto da aplicação. A mensagem vazia impede
      // que páginas antigas mostrem o mesmo erro novamente em um bloco grande.
      throw new ApiError("", response.status);
    }

    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
