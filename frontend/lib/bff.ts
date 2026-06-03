// Client-side helper for talking to the BFF proxy. All app data flows through
// `/api/proxy/*`; the browser never sees tokens (docs/architecture/05 §12.8).

export type Problem = { title?: string; detail?: string; status?: number };

const CSRF_HEADER = "x-csrf-token";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

function readCsrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  const match = document.cookie.match(/(?:^|;\s*)tin_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : undefined;
}

export async function bffFetch(path: string, init?: RequestInit): Promise<Response> {
  const method = (init?.method ?? "GET").toUpperCase();
  const csrf = SAFE_METHODS.has(method) ? undefined : readCsrfToken();
  return fetch(`/api/proxy${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(csrf ? { [CSRF_HEADER]: csrf } : {}),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
}

export async function bffJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await bffFetch(path, init);
  if (!res.ok) {
    const problem = (await res.json().catch(() => ({}))) as Problem;
    throw Object.assign(new Error(problem.detail ?? problem.title ?? `Request failed (${res.status})`), {
      problem,
      status: res.status,
    });
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}
