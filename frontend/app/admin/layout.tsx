"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { bffJson } from "@/lib/bff";

interface Principal {
  id: string;
  email: string;
  role: string;
  company_id?: string | null;
}

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [principal, setPrincipal] = useState<Principal | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function checkAuth() {
      try {
        const me = await bffJson<Principal>("/auth/me");
        setPrincipal(me);
      } catch (err) {
        router.push("/login");
      } finally {
        setLoading(false);
      }
    }
    checkAuth();
  }, [router]);

  async function handleLogout() {
    await bffJson("/auth/logout", { method: "POST" }).catch(() => {});
    router.push("/login");
  }

  if (loading) {
    return <div className="flex items-center justify-center min-h-screen">Loading...</div>;
  }

  if (!principal) {
    return null;
  }

  const isPlatformAdmin = principal.role === "PLATFORM_OWNER" || principal.role === "PLATFORM_ADMIN";

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="w-64 border-r border-slate-200 bg-white shadow-sm">
        <div className="p-6">
          <p className="text-xs font-medium uppercase tracking-wide text-brand-secondary">
            BBI Consultancy
          </p>
          <h2 className="mt-2 text-xl font-bold text-brand-primary">Portal</h2>
          <p className="mt-4 text-sm text-slate-600">{principal.email}</p>
        </div>

        <nav className="space-y-1 px-4 py-6">
          {isPlatformAdmin ? (
            <Link
              href="/admin/companies"
              className="block rounded px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
            >
              Companies
            </Link>
          ) : (
            <>
              <Link
                href="/admin/dashboard"
                className="block rounded px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
              >
                Dashboard
              </Link>
              <Link
                href="/admin/branding"
                className="block rounded px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
              >
                Branding
              </Link>
              <Link
                href="/admin/settings"
                className="block rounded px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
              >
                Settings
              </Link>
              <Link
                href="/admin/users"
                className="block rounded px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
              >
                Users
              </Link>
            </>
          )}
        </nav>

        <div className="border-t border-slate-200 p-4">
          <button
            onClick={handleLogout}
            className="w-full rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200"
          >
            Logout
          </button>
        </div>
      </aside>

      <main className="flex-1">
        <div className="p-8">{children}</div>
      </main>
    </div>
  );
}
