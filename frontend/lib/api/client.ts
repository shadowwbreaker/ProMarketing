/** Typed API client. Errors follow backend format {error: {code, message, details, request_id}}. */

export const API_URL =
  (typeof window === "undefined" ? process.env.API_INTERNAL_URL : undefined) ??
  (process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000").replace(/\/+$/, ""); // "/" = same origin (Vercel proxy)

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: Record<string, unknown> = {},
    public requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function readCookie(name: string): string | undefined {
  if (typeof document === "undefined") return undefined;
  return document.cookie
    .split("; ")
    .find((c) => c.startsWith(`${name}=`))
    ?.split("=")[1];
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export async function apiFetch<T>(
  path: string,
  options: { method?: Method; body?: unknown; signal?: AbortSignal; idempotencyKey?: string } = {},
): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  const isForm = typeof FormData !== "undefined" && options.body instanceof FormData;
  if (options.body !== undefined && !isForm) headers["Content-Type"] = "application/json";
  if (method !== "GET") {
    const csrf = readCookie("csrftoken");
    if (csrf) headers["X-CSRFToken"] = decodeURIComponent(csrf);
  }
  if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;

  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1${path}`, {
      method,
      headers,
      body: isForm ? (options.body as FormData) : options.body !== undefined ? JSON.stringify(options.body) : undefined,
      credentials: "include",
      signal: options.signal,
    });
  } catch {
    throw new ApiError(0, "network_error", "Нет связи с сервером");
  }

  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err = data?.error;
    throw new ApiError(
      res.status,
      err?.code ?? "http_error",
      err?.message ?? `Ошибка ${res.status}`,
      err?.details ?? {},
      err?.request_id,
    );
  }
  return data as T;
}

export type HealthReady = { status: "ok" | "degraded"; checks: Record<string, "ok" | "error"> };
export const getHealth = (signal?: AbortSignal) => apiFetch<HealthReady>("/health/ready", { signal });
