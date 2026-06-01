// Client-side helper for talking to the BFF proxy. All app data flows through
// `/api/proxy/*`; the browser never sees tokens (docs/architecture/05 §12.8).

export type Problem = { title?: string; detail?: string; status?: number };

export async function bffFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`/api/proxy${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
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
