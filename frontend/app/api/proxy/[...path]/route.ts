import { NextRequest, NextResponse } from "next/server";
import {
  ACCESS_COOKIE,
  API_INTERNAL,
  REFRESH_COOKIE,
  accessCookieOptions,
  refreshCookieOptions,
} from "@/lib/server/backend";

// Authenticated reverse proxy: attaches the access token from the httpOnly cookie
// to the backend call. On 401 it transparently rotates the refresh token once and
// retries, persisting the new cookies (docs/architecture/05 §12.8).

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
  return res;
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
