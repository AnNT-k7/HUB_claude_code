const DEFAULT_API_BASE_URL = "http://localhost:8000/api/v1";
const DEFAULT_TIMEOUT_MS = 30_000;

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? DEFAULT_API_BASE_URL
).replace(/\/+$/, "");

interface FastApiErrorBody {
  detail?: unknown;
  message?: unknown;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function errorMessage(details: unknown, fallback: string): string {
  if (!isRecord(details)) {
    return typeof details === "string" && details.trim() ? details : fallback;
  }

  const body = details as FastApiErrorBody;
  if (typeof body.message === "string" && body.message.trim()) {
    return body.message;
  }
  if (typeof body.detail === "string" && body.detail.trim()) {
    return body.detail;
  }
  if (Array.isArray(body.detail)) {
    const messages = body.detail
      .map((item) => {
        if (!isRecord(item) || typeof item.msg !== "string") {
          return null;
        }
        return item.msg;
      })
      .filter((item): item is string => item !== null);
    if (messages.length > 0) {
      return messages.join("; ");
    }
  }
  return fallback;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly details: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface ApiRequestOptions
  extends Omit<RequestInit, "body" | "method"> {
  timeoutMs?: number;
}

interface RequestOptions extends ApiRequestOptions {
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: BodyInit;
}

function buildUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}

async function parseBody(response: Response): Promise<unknown> {
  if (response.status === 204 || response.status === 205) {
    return undefined;
  }

  const text = await response.text();
  if (!text) {
    return undefined;
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return text;
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    throw new ApiError("Máy chủ trả về JSON không hợp lệ.", response.status, text);
  }
}

async function request<TResponse>(
  path: string,
  options: RequestOptions,
): Promise<TResponse> {
  const {
    timeoutMs = DEFAULT_TIMEOUT_MS,
    signal: externalSignal,
    headers: inputHeaders,
    ...fetchOptions
  } = options;
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  const handleExternalAbort = () => controller.abort(externalSignal?.reason);
  externalSignal?.addEventListener("abort", handleExternalAbort, { once: true });

  try {
    const headers = new Headers(inputHeaders);
    const demoOfficerId = process.env.NEXT_PUBLIC_OFFICER_ID?.trim();
    if (demoOfficerId && !headers.has("X-Officer-ID")) {
      headers.set("X-Officer-ID", demoOfficerId);
    }
    const response = await fetch(buildUrl(path), {
      ...fetchOptions,
      credentials: "include",
      headers,
      signal: controller.signal,
    });
    const details = await parseBody(response);

    if (!response.ok) {
      const fallback = `Yêu cầu thất bại với mã ${response.status}.`;
      throw new ApiError(errorMessage(details, fallback), response.status, details);
    }

    return details as TResponse;
  } catch (error: unknown) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (controller.signal.aborted) {
      throw new ApiError(
        externalSignal?.aborted
          ? "Yêu cầu đã được hủy."
          : "Yêu cầu quá thời gian chờ.",
        0,
        error,
      );
    }
    throw new ApiError("Không thể kết nối tới máy chủ.", 0, error);
  } finally {
    window.clearTimeout(timeoutId);
    externalSignal?.removeEventListener("abort", handleExternalAbort);
  }
}

function jsonBody<TBody>(body: TBody): { body: string; headers: Headers } {
  const headers = new Headers({
    Accept: "application/json",
    "Content-Type": "application/json",
  });
  return { body: JSON.stringify(body), headers };
}

export const apiClient = {
  get: <TResponse>(path: string, options: ApiRequestOptions = {}) =>
    request<TResponse>(path, { ...options, method: "GET" }),

  post: <TResponse, TBody = undefined>(
    path: string,
    body?: TBody,
    options: ApiRequestOptions = {},
  ) => {
    if (body === undefined) {
      return request<TResponse>(path, { ...options, method: "POST" });
    }
    const payload = jsonBody(body);
    const headers = new Headers(options.headers);
    payload.headers.forEach((value, key) => {
      if (!headers.has(key)) {
        headers.set(key, value);
      }
    });
    return request<TResponse>(path, {
      ...options,
      method: "POST",
      headers,
      body: payload.body,
    });
  },

  put: <TResponse, TBody>(
    path: string,
    body: TBody,
    options: ApiRequestOptions = {},
  ) => {
    const payload = jsonBody(body);
    return request<TResponse>(path, {
      ...options,
      method: "PUT",
      headers: payload.headers,
      body: payload.body,
    });
  },

  patch: <TResponse, TBody>(
    path: string,
    body: TBody,
    options: ApiRequestOptions = {},
  ) => {
    const payload = jsonBody(body);
    return request<TResponse>(path, {
      ...options,
      method: "PATCH",
      headers: payload.headers,
      body: payload.body,
    });
  },

  delete: <TResponse>(path: string, options: ApiRequestOptions = {}) =>
    request<TResponse>(path, { ...options, method: "DELETE" }),

  upload: <TResponse>(
    path: string,
    formData: FormData,
    options: ApiRequestOptions = {},
  ) => {
    const headers = new Headers(options.headers);
    headers.set("Accept", "application/json");
    return request<TResponse>(path, {
      ...options,
      method: "POST",
      headers,
      body: formData,
      timeoutMs: options.timeoutMs ?? 120_000,
    });
  },
};
