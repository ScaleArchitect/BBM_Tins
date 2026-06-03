import { NextRequest, NextResponse } from "next/server";
import { ACCESS_COOKIE, API_INTERNAL, CSRF_COOKIE, REFRESH_COOKIE } from "@/lib/server/backend";

// BFF logout: revoke the refresh-token family server-side, then clear cookies.
export async function POST(req: NextRequest) {
  const refresh = req.cookies.get(REFRESH_COOKIE)?.value;
  const access = req.cookies.get(ACCESS_COOKIE)?.value;
  if (refresh) {
    await fetch(`${API_INTERNAL}/auth/logout`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(access ? { Authorization: `Bearer ${access}` } : {}),
      },
      body: JSON.stringify({ refresh_token: refresh }),
      cache: "no-store",
    }).catch(() => undefined);
  }
  const res = NextResponse.json({ ok: true });
  res.cookies.delete(ACCESS_COOKIE);
  res.cookies.delete(REFRESH_COOKIE);
  res.cookies.delete(CSRF_COOKIE);
  return res;
}
