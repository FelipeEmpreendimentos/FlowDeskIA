import {
  clearSession,
  getToken,
  saveAccessToken,
} from "./auth";

const API_URL = import.meta.env.PROD
  ? "/api/v1"
  : import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

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

interface ApiValidationIssue {
  msg?: string;
  loc?: Array<string | number>;
  type?: string;
  ctx?: Record<string, unknown>;
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

const duplicateRegistryPrefixes = ["/clientes", "/servicos", "/usuarios"];
const phoneFields = new Set(["telefone", "whatsapp"]);

const fieldLabels: Record<string, string> = {
  nome: "Nome",
  email: "E-mail",
  telefone: "Telefone",
  whatsapp: "WhatsApp",
  senha: "Senha",
  nova_senha: "Nova senha",
  confirmar_senha: "Confirmação da senha",
  descricao: "Descrição",
  duracao_minutos: "Duração",
  preco: "Preço",
};

let refreshPromise: Promise<boolean> | null = null;
const inFlightGetRequests = new Map<string, Promise<unknown>>();

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

function normalizePhoneFields(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(normalizePhoneFields);
  }

  if (!value || typeof value !== "object") {
    return value;
  }

  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>).map(([key, item]) => {
      if (phoneFields.has(key) && typeof item === "string") {
        const digits = item.replace(/\D/g, "").slice(0, 11);
        return [key, digits || null];
      }
      return [key, normalizePhoneFields(item)];
    }),
  );
}

function normalizeRequestBody(body: BodyInit | null | undefined): BodyInit | null | undefined {
  if (typeof body !== "string") return body;

  try {
    return JSON.stringify(normalizePhoneFields(JSON.parse(body)));
  } catch {
    return body;
  }
}

async function fetchApi(
  endpoint: string,
  options: RequestInit,
  token: string | null,
): Promise<Response> {
  const headers = new Headers(options.headers);
  const body = normalizeRequestBody(options.body);

  if (body && !(body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  } else {
    headers.delete("Authorization");
  }

  return fetch(`${API_URL}${endpoint}`, {
    ...options,
    body,
    credentials: options.credentials ?? "include",
    cache: options.cache ?? "no-store",
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
        cache: "no-store",
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

function validationMessage(issue: ApiValidationIssue): string {
  const field = String(issue.loc?.at(-1) ?? "campo");
  const label = fieldLabels[field] ?? "Campo informado";
  const maxLength = Number(issue.ctx?.max_length ?? 0);
  const minLength = Number(issue.ctx?.min_length ?? 0);

  if (issue.type === "string_too_long") {
    return maxLength
      ? `${label} deve ter no máximo ${maxLength} caracteres.`
      : `${label} ultrapassou o tamanho permitido.`;
  }

  if (issue.type === "string_too_short") {
    return minLength
      ? `${label} deve ter pelo menos ${minLength} caracteres.`
      : `${label} está muito curto.`;
  }

  if (issue.type === "missing") {
    return `${label} é obrigatório.`;
  }

  if (issue.type === "value_error") {
    return issue.msg?.replace(/^Value error,\s*/i, "") || "Confira o valor informado.";
  }

  const englishMax = issue.msg?.match(/at most\s+(\d+)\s+characters/i);
  if (englishMax) {
    return `${label} deve ter no máximo ${englishMax[1]} caracteres.`;
  }

  const englishMin = issue.msg?.match(/at least\s+(\d+)\s+characters/i);
  if (englishMin) {
    return `${label} deve ter pelo menos ${englishMin[1]} caracteres.`;
  }

  return "Confira os dados informados e tente novamente.";
}

async function mensagemErro(response: Response): Promise<string> {
  let message = "Não foi possível concluir a solicitação.";

  try {
    const error = (await response.json()) as {
      detail?: string | ApiValidationIssue[];
    };

    if (typeof error.detail === "string") {
      message = error.detail;
    } else if (Array.isArray(error.detail) && error.detail.length > 0) {
      message = validationMessage(error.detail[0]);
    }
  } catch {
    // Mantém a mensagem padrão quando a API não retorna JSON.
  }

  return message;
}

function isRegistryDuplicate(endpoint: string, statusCode: number, message: string): boolean {
  if (statusCode !== 409 || !/^Já existe\b/i.test(message)) return false;
  const path = endpoint.split("?")[0];
  return duplicateRegistryPrefixes.some(
    (prefix) => path === prefix || path.startsWith(`${prefix}/`),
  );
}

function isContactValidation(statusCode: number, message: string): boolean {
  return (
    statusCode === 422 &&
    /^(WhatsApp|Telefone) deve conter DDD \+ número com 8 ou 9 dígitos/i.test(message)
  );
}

async function executeApiRequest<T>(
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

    if (isRegistryDuplicate(endpoint, response.status, message)) {
      emitAppToast({
        type: "warning",
        title: "Cadastro já existente",
        message,
      });
      throw new ApiError("", response.status);
    }

    if (isContactValidation(response.status, message)) {
      emitAppToast({
        type: "warning",
        title: message.startsWith("WhatsApp")
          ? "Confira o WhatsApp"
          : "Confira o telefone",
        message,
      });
      throw new ApiError("", response.status);
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

      throw new ApiError("", response.status);
    }

    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

function inFlightKey(endpoint: string, options: RequestInit): string | null {
  const method = (options.method ?? "GET").toUpperCase();
  if (method !== "GET" || options.body != null) return null;

  const headers = Array.from(new Headers(options.headers).entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => `${key}:${value}`)
    .join("|");

  return `${getToken() ?? "anon"}|${endpoint}|${headers}`;
}

export function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const key = inFlightKey(endpoint, options);
  if (!key) return executeApiRequest<T>(endpoint, options);

  const existing = inFlightGetRequests.get(key);
  if (existing) return existing as Promise<T>;

  const request = executeApiRequest<T>(endpoint, options).finally(() => {
    inFlightGetRequests.delete(key);
  });
  inFlightGetRequests.set(key, request);
  return request;
}
