export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;

  constructor(message: string, status: number, code = "error", details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

type ErrorEnvelope = {
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
  };
};

export function buildQuery(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue;
    search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  const isFormData = typeof FormData !== "undefined" && init.body instanceof FormData;
  if (init.body && !isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  headers.set("Accept", "application/json");

  const response = await fetch(`/api/proxy${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    let code = "error";
    let details: unknown;
    try {
      const payload = (await response.json()) as ErrorEnvelope;
      message = payload.error?.message ?? message;
      code = payload.error?.code ?? code;
      details = payload.error?.details;
    } catch {
      // keep the fallback message
    }
    throw new ApiError(message, response.status, code, details);
  }

  if (typeof window !== "undefined" && !["GET", "HEAD"].includes(method)) {
    window.dispatchEvent(new Event("hisaab:data-changed"));
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (Array.isArray(error.details) && error.details.length > 0) {
      const first = error.details[0] as { field?: string; message?: string };
      if (first?.message) {
        return first.field ? `${first.field}: ${first.message}` : first.message;
      }
    }
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return "Something went wrong. Please try again.";
}

/** Triggers a browser download from a proxied CSV endpoint. */
export async function downloadCsv(path: string, fallbackName: string): Promise<void> {
  const response = await fetch(`/api/proxy${path}`, { cache: "no-store" });
  if (!response.ok) {
    let message = `Export failed (${response.status})`;
    try {
      const payload = (await response.json()) as ErrorEnvelope;
      message = payload.error?.message ?? message;
    } catch {
      // ignore
    }
    throw new ApiError(message, response.status);
  }
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = /filename="?([^";]+)"?/i.exec(disposition);
  const filename = match?.[1] ?? fallbackName;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
