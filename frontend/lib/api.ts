const fallbackBaseUrl = "http://localhost:3000";

const getBackendBaseUrl = () => {
  if (process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL;
  }
  if (typeof window === "undefined") {
    return fallbackBaseUrl;
  }
  return window.location.origin || fallbackBaseUrl;
};

export const API_BASE_URL = getBackendBaseUrl();

type ApiOptions = RequestInit & {
  json?: unknown;
};

export async function apiFetch<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const { json, headers, ...rest } = options;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(headers || {})
    },
    body: json !== undefined ? JSON.stringify(json) : undefined,
    ...rest
  });

  if (!response.ok) {
    const contentType = response.headers.get("content-type") || "";
    let message = "";
    if (contentType.includes("application/json")) {
      try {
        const data = await response.json();
        if (data && typeof data === "object") {
          message =
            (data as { detail?: string }).detail ||
            JSON.stringify(data);
        }
      } catch (err) {
        message = "";
      }
    } else {
      try {
        const text = await response.text();
        if (text.trim().startsWith("{")) {
          const data = JSON.parse(text) as { detail?: string };
          message = data?.detail || text;
        } else {
          message = text;
        }
      } catch (err) {
        message = "";
      }
    }
    throw new Error(message || `Request failed with ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
