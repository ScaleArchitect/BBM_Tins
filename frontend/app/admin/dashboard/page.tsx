"use client";

export default function DashboardPage() {
  return (
    <div className="max-w-4xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">Dashboard</h1>
        <p className="mt-2 text-slate-600">Company overview</p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-slate-900">Users</h2>
          <p className="mt-2 text-3xl font-bold text-brand-primary">0</p>
          <p className="mt-1 text-sm text-slate-600">Manage in Users page</p>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-slate-900">Branding</h2>
          <p className="mt-2 text-sm text-slate-600">Configure in Branding page</p>
        </div>
      </div>
    </div>
  );
}
