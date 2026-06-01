"use client";

import { useEffect, useState, FormEvent } from "react";
import { bffJson } from "@/lib/bff";

interface Settings {
  reminder_days_before?: number;
  overdue_days_threshold?: number;
  allowed_cert_types?: string[];
  group_policy?: string;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    loadSettings();
  }, []);

  async function loadSettings() {
    try {
      const data = await bffJson<Settings>("/admin/settings");
      setSettings(data || {});
    } catch (err) {
      setError("Failed to load settings");
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
      await bffJson("/admin/settings", {
        method: "PUT",
        body: JSON.stringify(settings),
      });
      setSuccess("Settings updated successfully");
    } catch (err: unknown) {
      const error = err as Error & { problem?: { detail?: string } };
      setError(error.problem?.detail || error.message || "Failed to update settings");
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
        <h1 className="text-3xl font-bold text-slate-900">Settings</h1>
        <p className="mt-2 text-slate-600">Configure company policies</p>
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
          <label htmlFor="reminder_days_before" className="block text-sm font-medium text-slate-700">
            Reminder Days Before Expiry
          </label>
          <input
            id="reminder_days_before"
            type="number"
            value={settings.reminder_days_before || 0}
            onChange={(e) => setSettings({ ...settings, reminder_days_before: parseInt(e.target.value) })}
            className="mt-1 w-full rounded-lg border border-slate-300 px-4 py-2 text-sm"
          />
          <p className="mt-1 text-xs text-slate-500">Number of days before certificate expiry to send reminders</p>
        </div>

        <div>
          <label htmlFor="overdue_days_threshold" className="block text-sm font-medium text-slate-700">
            Overdue Days Threshold
          </label>
          <input
            id="overdue_days_threshold"
            type="number"
            value={settings.overdue_days_threshold || 0}
            onChange={(e) => setSettings({ ...settings, overdue_days_threshold: parseInt(e.target.value) })}
            className="mt-1 w-full rounded-lg border border-slate-300 px-4 py-2 text-sm"
          />
          <p className="mt-1 text-xs text-slate-500">Number of days after expiry to mark as overdue</p>
        </div>

        <div>
          <label htmlFor="allowed_cert_types" className="block text-sm font-medium text-slate-700">
            Allowed Certificate Types
          </label>
          <textarea
            id="allowed_cert_types"
            value={(settings.allowed_cert_types || []).join(", ")}
            onChange={(e) =>
              setSettings({
                ...settings,
                allowed_cert_types: e.target.value.split(",").map((s) => s.trim()),
              })
            }
            className="mt-1 w-full rounded-lg border border-slate-300 px-4 py-2 text-sm font-mono"
            rows={3}
          />
          <p className="mt-1 text-xs text-slate-500">Comma-separated list</p>
        </div>

        <div>
          <label htmlFor="group_policy" className="block text-sm font-medium text-slate-700">
            Group Policy
          </label>
          <textarea
            id="group_policy"
            value={settings.group_policy || ""}
            onChange={(e) => setSettings({ ...settings, group_policy: e.target.value })}
            className="mt-1 w-full rounded-lg border border-slate-300 px-4 py-2 text-sm"
            rows={4}
          />
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
