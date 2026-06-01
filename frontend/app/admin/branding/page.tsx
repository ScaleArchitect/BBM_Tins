"use client";

import { useEffect, useState, FormEvent } from "react";
import { bffJson } from "@/lib/bff";

interface Branding {
  primary_color?: string;
  secondary_color?: string;
  welcome_text?: string;
  support_email?: string;
  locale?: string;
}

export default function BrandingPage() {
  const [branding, setBranding] = useState<Branding>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    loadBranding();
  }, []);

  async function loadBranding() {
    try {
      const data = await bffJson<Branding>("/admin/branding");
      setBranding(data || {});
    } catch (err) {
      setError("Failed to load branding");
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setSaving(true);

    try {
      await bffJson("/admin/branding", {
        method: "PUT",
        body: JSON.stringify(branding),
      });
      setSuccess("Branding updated successfully");
    } catch (err: unknown) {
      const error = err as Error & { problem?: { detail?: string } };
      setError(error.problem?.detail || error.message || "Failed to update branding");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p className="text-slate-600">Loading...</p>;
  }

  return (
    <div className="max-w-2xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">Branding</h1>
        <p className="mt-2 text-slate-600">Customize your company appearance</p>
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

      <form onSubmit={handleSubmit} className="rounded-lg border border-slate-200 bg-white p-6 space-y-6">
        <div>
          <label htmlFor="primary_color" className="block text-sm font-medium text-slate-700">
            Primary Color
          </label>
          <input
            id="primary_color"
            type="text"
            placeholder="#0066FF"
            value={branding.primary_color || ""}
            onChange={(e) => setBranding({ ...branding, primary_color: e.target.value })}
            className="mt-1 w-full rounded-lg border border-slate-300 px-4 py-2 text-sm font-mono"
          />
          <p className="mt-1 text-xs text-slate-500">Hex color code</p>
        </div>

        <div>
          <label htmlFor="secondary_color" className="block text-sm font-medium text-slate-700">
            Secondary Color
          </label>
          <input
            id="secondary_color"
            type="text"
            placeholder="#666666"
            value={branding.secondary_color || ""}
            onChange={(e) => setBranding({ ...branding, secondary_color: e.target.value })}
            className="mt-1 w-full rounded-lg border border-slate-300 px-4 py-2 text-sm font-mono"
          />
          <p className="mt-1 text-xs text-slate-500">Hex color code</p>
        </div>

        <div>
          <label htmlFor="welcome_text" className="block text-sm font-medium text-slate-700">
            Welcome Text
          </label>
          <textarea
            id="welcome_text"
            value={branding.welcome_text || ""}
            onChange={(e) => setBranding({ ...branding, welcome_text: e.target.value })}
            className="mt-1 w-full rounded-lg border border-slate-300 px-4 py-2 text-sm"
            rows={4}
          />
        </div>

        <div>
          <label htmlFor="support_email" className="block text-sm font-medium text-slate-700">
            Support Email
          </label>
          <input
            id="support_email"
            type="email"
            value={branding.support_email || ""}
            onChange={(e) => setBranding({ ...branding, support_email: e.target.value })}
            className="mt-1 w-full rounded-lg border border-slate-300 px-4 py-2 text-sm"
          />
        </div>

        <div>
          <label htmlFor="locale" className="block text-sm font-medium text-slate-700">
            Locale
          </label>
          <select
            id="locale"
            value={branding.locale || "en-US"}
            onChange={(e) => setBranding({ ...branding, locale: e.target.value })}
            className="mt-1 w-full rounded-lg border border-slate-300 px-4 py-2 text-sm"
          >
            <option value="en-US">English (US)</option>
            <option value="ar-AE">Arabic (UAE)</option>
          </select>
        </div>

        <button
          type="submit"
          disabled={saving}
          className="w-full rounded-lg bg-brand-primary px-4 py-2 text-sm font-medium text-white hover:bg-brand-primary/90 disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save Changes"}
        </button>
      </form>
    </div>
  );
}
