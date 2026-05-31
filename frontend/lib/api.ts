import { API_BASE } from "./config";

// Thin fetch helper. The frontend holds NO business logic — it only talks to the
// backend (docs/architecture/05 §12.1). Auth/BFF wiring arrives in later sprints.
export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status}`);
  }
  return (await res.json()) as T;
}
