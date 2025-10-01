const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function handle<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {})
    }
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return (await res.json()) as T;
}

export function apiGet<T>(path: string): Promise<T> {
  return handle<T>(path, { cache: "no-store" });
}

export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return handle<T>(path, {
    method: "POST",
    body: JSON.stringify(body)
  });
}

export { API_BASE };
