"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { bffJson, Problem } from "@/lib/bff";

interface LoginFormData {
  email: string;
  password: string;
}

export default function LoginPage() {
  const router = useRouter();
  const [form, setForm] = useState<LoginFormData>({ email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const result = await bffJson("/auth/login", {
        method: "POST",
        body: JSON.stringify(form),
      });
      router.push("/admin");
    } catch (err: unknown) {
      const error = err as Error & { problem?: Problem };
      setError(error.problem?.detail || error.message || "Login failed");
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-6 px-6">
      <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="text-sm font-medium uppercase tracking-wide text-brand-secondary">
          BBI Consultancy
        </p>
        <h1 className="mt-1 text-3xl font-bold text-brand-primary">
          Login
        </h1>

        {error && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-slate-700">
              Email
            </label>
            <input
              id="email"
              type="email"
              placeholder="admin@example.com"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              disabled={loading}
              className="mt-1 w-full rounded-lg border border-slate-300 px-4 py-2 text-sm focus:border-brand-primary focus:outline-none disabled:bg-slate-100"
              required
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-700">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              disabled={loading}
              className="mt-1 w-full rounded-lg border border-slate-300 px-4 py-2 text-sm focus:border-brand-primary focus:outline-none disabled:bg-slate-100"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="mt-6 w-full rounded-lg bg-brand-primary px-4 py-2 font-medium text-white hover:bg-brand-primary/90 disabled:opacity-50"
          >
            {loading ? "Logging in..." : "Login"}
          </button>
        </form>
      </div>
    </main>
  );
}
