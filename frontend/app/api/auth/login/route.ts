import { NextRequest, NextResponse } from "next/server";
import {
  ACCESS_COOKIE,
  API_INTERNAL,
  CSRF_COOKIE,
  REFRESH_COOKIE,
  accessCookieOptions,
  csrfCookieOptions,
  newCsrfToken,
  refreshCookieOptions,
} from "@/lib/server/backend";

// BFF login: forwards credentials to the backend, then stores the returned
// access + refresh tokens in httpOnly cookies and returns only the non-sensitive
// principal info to the browser.
export async function POST(req: NextRequest) {
  const body = await req.json();
  const r = await fetch(`${API_INTERNAL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    return NextResponse.json(data, { status: r.status });
  }
  const res = NextResponse.json({ principal: data.principal });
  res.cookies.set(ACCESS_COOKIE, data.access_token, accessCookieOptions(data.expires_in));
  res.cookies.set(REFRESH_COOKIE, data.refresh_token, refreshCookieOptions());
  res.cookies.set(CSRF_COOKIE, newCsrfToken(), csrfCookieOptions());
  return res;
}
