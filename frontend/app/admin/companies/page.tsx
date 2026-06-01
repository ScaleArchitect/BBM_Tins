"use client";

import { useEffect, useState, FormEvent } from "react";
import { bffJson } from "@/lib/bff";

interface Company {
  id: string;
  slug: string;
  status: "ONBOARDING" | "ACTIVE" | "SUSPENDED";
  subscription_tier: "FREE" | "PRO" | "ENTERPRISE";
}

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ slug: "" });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadCompanies();
  }, []);

  async function loadCompanies() {
    try {
      const list = await bffJson<Company[]>("/platform/companies");
      setCompanies(list || []);
    } catch (err) {
      setError("Failed to load companies");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateCompany(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    try {
      const result = await bffJson("/platform/companies", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setForm({ slug: "" });
      setShowForm(false);
      await loadCompanies();
    } catch (err: unknown) {
      const error = err as Error & { problem?: { detail?: string } };
      setError(error.problem?.detail || error.message || "Failed to create company");
    }
  }

  return (
    <div className="max-w-4xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">Companies</h1>
        <p className="mt-2 text-slate-600">Manage tenant companies</p>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {showForm && (
        <div className="mb-8 rounded-lg border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">Create Company</h2>
          <form onSubmit={handleCreateCompany} className="space-y-4">
            <div>
              <label htmlFor="slug" className="block text-sm font-medium text-slate-700">
                Company Slug
              </label>
              <input
                id="slug"
                type="text"
                placeholder="acme-corp"
                value={form.slug}
                onChange={(e) => setForm({ slug: e.target.value })}
                className="mt-1 w-full rounded-lg border border-slate-300 px-4 py-2 text-sm"
                required
              />
              <p className="mt-1 text-xs text-slate-500">DNS-label safe (lowercase, hyphens only)</p>
            </div>
            <div className="flex gap-2">
              <button
                type="submit"
                className="rounded-lg bg-brand-primary px-4 py-2 text-sm font-medium text-white hover:bg-brand-primary/90"
              >
                Create
              </button>
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {!showForm && (
        <button
          onClick={() => setShowForm(true)}
          className="mb-8 rounded-lg bg-brand-primary px-4 py-2 text-sm font-medium text-white hover:bg-brand-primary/90"
        >
          + Create Company
        </button>
      )}

      {loading ? (
        <p className="text-slate-600">Loading companies...</p>
      ) : companies.length === 0 ? (
        <p className="text-slate-600">No companies yet</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 bg-slate-50">
              <tr>
                <th className="px-6 py-3 text-left font-semibold text-slate-900">Slug</th>
                <th className="px-6 py-3 text-left font-semibold text-slate-900">Status</th>
                <th className="px-6 py-3 text-left font-semibold text-slate-900">Tier</th>
              </tr>
            </thead>
            <tbody>
              {companies.map((company) => (
                <tr key={company.id} className="border-b border-slate-200 hover:bg-slate-50">
                  <td className="px-6 py-4 text-slate-900">{company.slug}</td>
                  <td className="px-6 py-4">
                    <span className="inline-flex rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-800">
                      {company.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-slate-700">{company.subscription_tier}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
