/* Client-side auth: bearer token persistence, public auth config, and a
 * global fetch interceptor that attaches `Authorization` to every API call.
 *
 * The interceptor is installed at module scope so it is guaranteed to be in
 * place before any page effect fires (React runs child effects before parent
 * effects). It only touches requests to the configured API base — everything
 * else passes through untouched.
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TOKEN_KEY = "cmpdi-token";

export type AuthConfig = {
  auth_enabled: boolean;
  demo_users: Record<string, string>;
};

let cachedConfig: AuthConfig | null = null;

function safeStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function getToken(): string | null {
  return safeStorage()?.getItem(TOKEN_KEY) ?? null;
}

export function setToken(token: string): void {
  safeStorage()?.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  safeStorage()?.removeItem(TOKEN_KEY);
}

export async function fetchAuthConfig(): Promise<AuthConfig> {
  if (cachedConfig) return cachedConfig;
  const res = await fetch(`${API_BASE}/api/v1/auth/config`);
  if (!res.ok) {
    throw new Error(`Auth config request failed (${res.status})`);
  }
  cachedConfig = (await res.json()) as AuthConfig;
  return cachedConfig;
}

const _originalFetch =
  typeof window === "undefined" ? null : window.fetch.bind(window);

if (typeof window !== "undefined" && _originalFetch) {
  window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    const url =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.href
          : input.url;
    const token = getToken();
    if (token && url.startsWith(API_BASE)) {
      const headers = new Headers(init?.headers);
      if (!headers.has("Authorization")) {
        headers.set("Authorization", `Bearer ${token}`);
      }
      return _originalFetch(input, { ...init, headers });
    }
    return _originalFetch(input, init);
  };
}