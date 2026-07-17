const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

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

export interface ApiRequestOptions<TBody = unknown>
  extends Omit<RequestInit, "body"> {
  body?: TBody;
}

async function request<TResponse, TBody = never>(
  path: string,
  options: ApiRequestOptions<TBody> = {},
): Promise<TResponse> {
  const headers = new Headers(options.headers);
  const hasBody = options.body !== undefined;

  if (hasBody && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    body: hasBody ? JSON.stringify(options.body) : undefined,
  });
  const responseText = await response.text();

  if (!response.ok) {
    let details: unknown = responseText;
    try {
      details = responseText ? JSON.parse(responseText) : null;
    } catch {
      // Preserve a non-JSON response as text.
    }
    throw new ApiError(`API request failed with status ${response.status}`, response.status, details);
  }

  if (!responseText) {
    return undefined as TResponse;
  }

  return JSON.parse(responseText) as TResponse;
}

export const apiClient = {
  get: <TResponse>(path: string, options?: ApiRequestOptions<never>) =>
    request<TResponse>(path, { ...options, method: "GET" }),
  post: <TResponse, TBody>(path: string, body: TBody) =>
    request<TResponse, TBody>(path, { method: "POST", body }),
  put: <TResponse, TBody>(path: string, body: TBody) =>
    request<TResponse, TBody>(path, { method: "PUT", body }),
  delete: <TResponse>(path: string, options?: ApiRequestOptions<never>) =>
    request<TResponse>(path, { ...options, method: "DELETE" }),
};

