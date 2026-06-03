import { NextRequest, NextResponse } from "next/server";
import {
  ACCESS_COOKIE,
  API_INTERNAL,
  CSRF_COOKIE,
  CSRF_HEADER,
  REFRESH_COOKIE,
  accessCookieOptions,
  csrfCookieOptions,
  newCsrfToken,
  refreshCookieOptions,
} from "@/lib/server/backend";

// Authenticated reverse proxy: attaches the access token from the httpOnly cookie
// to the backend call. On 401 it transparently rotates the refresh token once and
// retries, persisting the new cookies (docs/architecture/05 §12.8).

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

async function rotate(refresh: string) {
  const r = await fetch(`${API_INTERNAL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
    cache: "no-store",
  });
  if (!r.ok) return null;
  return (await r.json()) as { access_token: string; refresh_token: string; expires_in: number };
}

async function handle(req: NextRequest, ctx: { params: { path: string[] } }) {
  const path = "/" + (ctx.params.path?.join("/") ?? "");

  // CSRF defence (double-submit): for unsafe methods the readable CSRF cookie
  // must match the x-csrf-token header set by the client. Blocks forged
  // cross-site requests that ride the httpOnly auth cookies. The /auth/*
  // credential endpoints are exempt: at first contact (login) no token exists
  // yet, and they are guarded by credentials rather than tenant-scoped data.
  const csrfCookie = req.cookies.get(CSRF_COOKIE)?.value;
  if (!SAFE_METHODS.has(req.method) && !path.startsWith("/auth/")) {
    const headerToken = req.headers.get(CSRF_HEADER);
    if (!csrfCookie || !headerToken || csrfCookie !== headerToken) {
      return NextResponse.json(
        { title: "Invalid CSRF token", status: 403 },
        { status: 403 },
      );
    }
  }

  const url = `${API_INTERNAL}${path}${req.nextUrl.search}`;
  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  const bodyText = hasBody ? await req.text() : undefined;

  const send = (token?: string) =>
    fetch(url, {
      method: req.method,
      headers: {
        "Content-Type": req.headers.get("content-type") ?? "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: bodyText,
      cache: "no-store",
    });

  let access = req.cookies.get(ACCESS_COOKIE)?.value;
  const refresh = req.cookies.get(REFRESH_COOKIE)?.value;

  let backendRes = await send(access);
  let rotated: { access_token: string; refresh_token: string; expires_in: number } | null = null;

  if (backendRes.status === 401 && refresh) {
    rotated = await rotate(refresh);
    if (rotated) {
      access = rotated.access_token;
      backendRes = await send(access);
    }
  }

  const text = await backendRes.text();
  const res = new NextResponse(text, {
    status: backendRes.status,
    headers: { "Content-Type": backendRes.headers.get("content-type") ?? "application/json" },
  });
  if (rotated) {
    res.cookies.set(ACCESS_COOKIE, rotated.access_token, accessCookieOptions(rotated.expires_in));
    res.cookies.set(REFRESH_COOKIE, rotated.refresh_token, refreshCookieOptions());
  }
  // Bootstrap the double-submit CSRF cookie on first contact so the client has a
  // readable token to echo on subsequent unsafe requests.
  if (!csrfCookie) {
    res.cookies.set(CSRF_COOKIE, newCsrfToken(), csrfCookieOptions());
  }
  return res;
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
