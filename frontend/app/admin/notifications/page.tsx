"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { useAdminSession, useAuditToast } from "@/app/admin/layout";
import {
  getAdminNotificationPlatformSettings,
  patchAdminNotificationPlatformSettings,
} from "@/lib/admin/api";
import { formatDigestHourLocal } from "@/lib/notifications";

export default function AdminNotificationsPage() {
  const { token } = useAdminSession();
  const { showAuditToast } = useAuditToast();
  const [hour, setHour] = useState(18);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    void load();
  }, [token]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await getAdminNotificationPlatformSettings(token!);
      setHour(res.job_alert_digest_hour_local);
      setUpdatedAt(res.updated_at);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load settings");
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    if (!token) return;
    setSaving(true);
    setError(null);
    try {
      const res = await patchAdminNotificationPlatformSettings(token, {
        job_alert_digest_hour_local: hour,
      });
      showAuditToast(res.audit_log_id);
      setHour(res.data.job_alert_digest_hour_local);
      setUpdatedAt(res.data.updated_at);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (!token) {
    return (
      <p className="text-slate-400 text-sm">Sign in at /admin/auth to manage notification settings.</p>
    );
  }

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-amber-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-lg">
      <div>
        <h1 className="text-xl font-semibold text-white">Notifications</h1>
        <p className="text-sm text-slate-400 mt-1">
          Platform defaults for Career Watch email delivery. Times apply in each user&apos;s own
          timezone (from their notification preferences).
        </p>
      </div>

      {error && (
        <div className="text-sm text-red-300 bg-red-950/40 border border-red-800 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      <section className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
        <h2 className="text-sm font-medium text-slate-200">Daily job-alert digest</h2>
        <label className="block text-sm text-slate-400" htmlFor="digest-hour">
          Send hour (0–23, local to each user)
        </label>
        <div className="flex flex-wrap items-center gap-3">
          <input
            id="digest-hour"
            type="number"
            min={0}
            max={23}
            value={hour}
            onChange={(e) => setHour(Number(e.target.value))}
            data-testid="admin-digest-hour"
            className="w-24 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white text-sm"
          />
          <span className="text-sm text-slate-300">
            Preview: {formatDigestHourLocal(hour)} in the user&apos;s timezone
          </span>
        </div>
        {updatedAt && (
          <p className="text-xs text-slate-500">Last updated {new Date(updatedAt).toLocaleString()}</p>
        )}
        <button
          type="button"
          disabled={saving}
          onClick={() => void handleSave()}
          data-testid="admin-digest-hour-save"
          className="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg"
        >
          {saving ? "Saving…" : "Save"}
        </button>
      </section>
    </div>
  );
}
