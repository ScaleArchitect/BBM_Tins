"use client";

import { useEffect, useState, FormEvent } from "react";
import { bffJson } from "@/lib/bff";

interface Admin {
  id: string;
  email: string;
  role: string;
  status: "ACTIVE" | "SUSPENDED";
}

export default function UsersPage() {
  const [admins, setAdmins] = useState<Admin[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ email: "", role: "COMPANY_ADMIN" });
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    loadAdmins();
  }, []);

  async function loadAdmins() {
    try {
      const list = await bffJson<Admin[]>("/admin/users");
      setAdmins(list || []);
    } catch (err) {
      setError("Failed to load users");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateAdmin(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    try {
      await bffJson("/admin/users", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setForm({ email: "", role: "COMPANY_ADMIN" });
      setShowForm(false);
      setSuccess("Admin user invited successfully");
      await loadAdmins();
    } catch (err: unknown) {
      const error = err as Error & { problem?: { detail?: string } };
      setError(error.problem?.detail || error.message || "Failed to create user");
    }
  }

  return (
    <div className="max-w-4xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">Users</h1>
        <p className="mt-2 text-slate-600">Manage company administrators</p>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {success && (
        <div className="mb-6 rounded-lg border border-green-200 bg-green-50 p-4">
          <p className="text-sm text-green-700">{success}</p>
        </div>
      )}

      {showForm && (
        <div className="mb-8 rounded-lg border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">Invite Admin</h2>
          <form onSubmit={handleCreateAdmin} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-slate-700">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="mt-1 w-full rounded-lg border border-slate-300 px-4 py-2 text-sm"
                required
              />
            </div>

            <div>
              <label htmlFor="role" className="block text-sm font-medium text-slate-700">
                Role
              </label>
              <select
                id="role"
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
                className="mt-1 w-full rounded-lg border border-slate-300 px-4 py-2 text-sm"
              >
                <option value="COMPANY_OWNER">Owner</option>
                <option value="COMPANY_ADMIN">Admin</option>
                <option value="COMPANY_VIEWER">Viewer</option>
              </select>
            </div>

            <div className="flex gap-2">
              <button
                type="submit"
                className="rounded-lg bg-brand-primary px-4 py-2 text-sm font-medium text-white hover:bg-brand-primary/90"
              >
                Invite
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
          + Invite Admin
        </button>
      )}

      {loading ? (
        <p className="text-slate-600">Loading...</p>
      ) : admins.length === 0 ? (
        <p className="text-slate-600">No administrators yet</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 bg-slate-50">
              <tr>
                <th className="px-6 py-3 text-left font-semibold text-slate-900">Email</th>
                <th className="px-6 py-3 text-left font-semibold text-slate-900">Role</th>
                <th className="px-6 py-3 text-left font-semibold text-slate-900">Status</th>
              </tr>
            </thead>
            <tbody>
              {admins.map((admin) => (
                <tr key={admin.id} className="border-b border-slate-200 hover:bg-slate-50">
                  <td className="px-6 py-4 text-slate-900">{admin.email}</td>
                  <td className="px-6 py-4">
                    <span className="inline-flex rounded-full bg-blue-100 px-2 py-1 text-xs font-semibold text-blue-800">
                      {admin.role}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-slate-700">{admin.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
