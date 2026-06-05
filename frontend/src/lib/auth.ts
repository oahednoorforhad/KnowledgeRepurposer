const TOKEN_KEY = "kp_token";

export function getToken(): string | null {
  return null;
}

export function setToken(_token: string): void {
  // No-op: tokens are now managed via HTTP-only cookies
}

export function clearToken(): void {
  // No-op: tokens are now managed via HTTP-only cookies
}

export function authHeaders(): Record<string, string> {
  return {};
}
