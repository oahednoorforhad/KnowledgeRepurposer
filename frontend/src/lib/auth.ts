// Auth lives in HttpOnly cookies set by the backend; the client never sees the tokens.
export const API_BASE = "http://localhost:8000";

// One in-flight refresh shared by all callers: the backend treats a second use of the
// same (already rotated) refresh token as reuse and revokes every session.
let refreshing: Promise<boolean> | null = null;

function refreshSession(): Promise<boolean> {
  refreshing ??= fetch(`${API_BASE}/auth/refresh`, { method: "POST", credentials: "include" })
    .then((r) => r.ok)
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

const NO_RETRY = new Set(["/auth/login", "/auth/register", "/auth/refresh"]);

// fetch against the API with cookies; on 401 refresh the access token once and retry.
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const opts: RequestInit = { ...init, credentials: "include" };
  const res = await fetch(`${API_BASE}${path}`, opts);
  if (res.status !== 401 || NO_RETRY.has(path)) return res;
  return (await refreshSession()) ? fetch(`${API_BASE}${path}`, opts) : res;
}
