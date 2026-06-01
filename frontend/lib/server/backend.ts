// Server-only BFF configuration. Tokens live in httpOnly cookies set here and are
// attached to backend calls server-side, so they never reach client JS
// (docs/architecture/05 §12.8).

export const API_INTERNAL =
  process.env.API_INTERNAL_URL ?? "http://localhost:8000/api/v1";

export const ACCESS_COOKIE = "tin_at";
export const REFRESH_COOKIE = "tin_rt";

const REFRESH_MAX_AGE = 60 * 60 * 24 * 7; // 7 days

export function accessCookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge,
  };
}

export function refreshCookieOptions() {
  return accessCookieOptions(REFRESH_MAX_AGE);
}
