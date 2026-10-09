"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Bug, Check, GraduationCap, Loader2, Mail, MessageCircle } from "lucide-react";
import { SUPPORT_EMAIL } from "@/lib/brand";
import { restartTutorial, setTutorialEnabled, isTutorialEnabled } from "@/lib/guidance/tutorial";
import { useRequireAuth } from "@/lib/auth/guards";
import { fetchMe, forgotPassword } from "@/lib/auth/api";
import { patchDisplayName, sendEmailVerification } from "@/lib/account";
import { friendlyAuthError } from "@/lib/auth/errors";
import { cn } from "@/lib/utils";

export default function SettingsPage() {
  const { session, status } = useRequireAuth("/settings");
  const token = session?.backendAccessToken;
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [verified, setVerified] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [verifySent, setVerifySent] = useState(false);
  const [authProvider, setAuthProvider] = useState("");
  const [resetSent, setResetSent] = useState(false);
  const [resetSending, setResetSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [verifySending, setVerifySending] = useState(false);
  const [tutorialTipsEnabled, setTutorialTipsEnabled] = useState(true);

  useEffect(() => {
    setTutorialTipsEnabled(isTutorialEnabled());
  }, []);

  useEffect(() => {
    if (loading) return;
    function scrollToHash() {
      const hash = window.location.hash;
      if (!hash) return;
      document.querySelector(hash)?.scrollIntoView({ block: "start" });
    }
    scrollToHash();
    window.addEventListener("hashchange", scrollToHash);
    return () => window.removeEventListener("hashchange", scrollToHash);
  }, [loading]);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const me = await fetchMe(token);
      setDisplayName(me.display_name);
      setEmail(me.email);
      setVerified(Boolean(me.email_verified_at));
      setAuthProvider(me.auth_provider);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  async function saveName() {
    if (!token || !displayName.trim()) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await patchDisplayName(token, displayName.trim());
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function resendVerification() {
    if (!token || verifySending) return;
    setVerifySending(true);
    setError(null);
    try {
      await sendEmailVerification(token);
      setVerifySent(true);
      await load();
    } catch (e) {
      const code = e instanceof Error ? e.message : "";
      setError(friendlyAuthError(code === "HTTP 429" ? "verify_send_rate_limited" : code));
    } finally {
      setVerifySending(false);
    }
  }

  if (status === "loading" || !token || loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-amber-700 dark:text-amber-400" />
      </div>
    );
  }

  return (
    <main className="max-w-2xl mx-auto px-4 py-8">
      <Link href="/dashboard" className="text-sm text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-300">
        ← Back to dashboard
      </Link>
      <h1 className="text-2xl font-semibold text-slate-900 dark:text-white mt-4 mb-2">Account settings</h1>
      <p className="text-sm text-slate-600 dark:text-slate-400 mb-8">
        Manage your profile, notifications, and data.
      </p>

      {error && (
        <p className="mb-4 text-sm text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900/50 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      <section className="mb-8 border border-slate-200 dark:border-slate-800 rounded-xl p-4 space-y-4">
        <h2 className="font-medium text-slate-800 dark:text-slate-200">Display name</h2>
        <input
          type="text"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 text-slate-800 dark:text-slate-200 text-sm"
        />
        <button
          type="button"
          onClick={() => void saveName()}
          disabled={saving}
          className={cn(
            "px-4 py-2 rounded-lg text-sm font-medium",
            saving
              ? "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400"
              : "bg-amber-400 text-slate-900 hover:bg-amber-300",
          )}
        >
          {saving ? "Saving…" : "Save name"}
        </button>
        {saved && (
          <p className="flex items-center gap-1 text-sm text-emerald-700 dark:text-emerald-400">
            <Check className="w-4 h-4" /> Saved
          </p>
        )}
      </section>

      <section
        id="email-verification"
        className="mb-8 border border-slate-200 dark:border-slate-800 rounded-xl p-4 space-y-3 scroll-mt-24"
      >
        <h2 className="font-medium text-slate-800 dark:text-slate-200">Email</h2>
        <p className="text-sm text-slate-600 dark:text-slate-400">{email}</p>
        {verified ? (
          <p className="flex items-center gap-2 text-sm text-emerald-700 dark:text-emerald-400">
            <Check className="w-4 h-4" /> Verified
          </p>
        ) : (
          <div className="space-y-2">
            <p className="text-sm text-amber-700 dark:text-amber-300">
              {verifySent
                ? "We sent a verification link to your inbox. Open it to unlock your credits and use AI features."
                : "Email not verified — send a link to your inbox to unlock AI features and credits."}
            </p>
            <button
              type="button"
              disabled={verifySending}
              onClick={() => void resendVerification()}
              className="inline-flex items-center gap-2 text-sm text-amber-700 dark:text-amber-400 hover:text-amber-800 dark:hover:text-amber-300"
            >
              <Mail className="w-4 h-4" />
              {verifySending
                ? "Sending…"
                : verifySent
                  ? "Resend verification email"
                  : "Send verification email"}
            </button>
          </div>
        )}
      </section>

      <section className="mb-8 border border-slate-200 dark:border-slate-800 rounded-xl p-4 space-y-3">
        <h2 className="font-medium text-slate-800 dark:text-slate-200">Password</h2>
        {authProvider === "email" ? (
          <>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              We will email you a link to choose a new password. The link expires
              in one hour and signs you out of other devices when you use it.
            </p>
            <button
              type="button"
              onClick={() => {
                setError(null);
                setResetSending(true);
                void forgotPassword(email)
                  .then(() => setResetSent(true))
                  .catch((e) =>
                    setError(
                      e instanceof Error
                        ? friendlyAuthError(e.message)
                        : "Could not send reset email",
                    ),
                  )
                  .finally(() => setResetSending(false));
              }}
              disabled={resetSending || resetSent}
              className="inline-flex items-center gap-2 text-sm text-amber-700 dark:text-amber-400 hover:text-amber-800 dark:hover:text-amber-300 disabled:opacity-60"
            >
              {resetSent ? "Reset email sent" : "Email me a password reset link"}
            </button>
          </>
        ) : (
          <p className="text-sm text-slate-600 dark:text-slate-400">
            You sign in with {authProvider || "SSO"}, so there is no password to
            change here.
          </p>
        )}
      </section>

      <section className="mb-8 border border-slate-200 dark:border-slate-800 rounded-xl p-4 space-y-2">
        <h2 className="font-medium text-slate-800 dark:text-slate-200">Browser extension</h2>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          Capture job postings from Greenhouse, Lever, and similar sites, or autofill applications
          from your tailored resume.
        </p>
        <Link
          href="/extension"
          className="text-sm text-amber-700 dark:text-amber-400 hover:text-amber-800 dark:hover:text-amber-300 font-medium"
        >
          Install or update the extension →
        </Link>
      </section>

      <section
        id="help-feedback"
        className="mb-8 border border-slate-200 dark:border-slate-800 rounded-xl p-4 space-y-3 scroll-mt-24"
      >
        <h2 className="font-medium text-slate-800 dark:text-slate-200">Help &amp; feedback</h2>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          Found a bug or something confusing? Tell us what you were doing and what went wrong — we read
          every report.
        </p>
        <div className="flex flex-col gap-2 text-sm">
          <Link
            href="/legal/contact?topic=bug_report"
            className="inline-flex items-center gap-2 text-amber-700 dark:text-amber-400 hover:text-amber-800 dark:hover:text-amber-300 font-medium"
          >
            <Bug className="w-4 h-4 shrink-0" aria-hidden />
            Report a bug
          </Link>
          <Link
            href="/legal/contact?topic=product_feedback"
            className="inline-flex items-center gap-2 text-amber-700 dark:text-amber-400 hover:text-amber-800 dark:hover:text-amber-300 font-medium"
          >
            <MessageCircle className="w-4 h-4 shrink-0" aria-hidden />
            Send product feedback
          </Link>
          <a
            href={`mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent("FlintApply support")}`}
            className="inline-flex items-center gap-2 text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white"
          >
            <Mail className="w-4 h-4 shrink-0" aria-hidden />
            Email {SUPPORT_EMAIL}
          </a>
        </div>
      </section>

      <section
        id="tutorial-tips"
        className="mb-8 border border-slate-200 dark:border-slate-800 rounded-xl p-4 space-y-3 scroll-mt-24"
      >
        <h2 className="font-medium text-slate-800 dark:text-slate-200 flex items-center gap-2">
          <GraduationCap className="w-4 h-4 text-amber-700 dark:text-amber-400" aria-hidden />
          Tutorial tips
        </h2>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          Step-by-step hints on the dashboard and job flows. Turn them off anytime or start over from
          the beginning.
        </p>
        <label className="flex items-center gap-2 cursor-pointer text-sm text-slate-700 dark:text-slate-300">
          <input
            type="checkbox"
            checked={tutorialTipsEnabled}
            onChange={(e) => {
              const next = e.target.checked;
              setTutorialEnabled(next);
              setTutorialTipsEnabled(next);
            }}
            className="rounded border-slate-400 text-amber-600 focus:ring-amber-400"
          />
          Show step tips on dashboard and job flows
        </label>
        <button
          type="button"
          className="text-sm font-medium text-amber-700 dark:text-amber-400 hover:text-amber-800 dark:hover:text-amber-300"
          onClick={() => {
            restartTutorial();
          }}
        >
          Restart tutorial
        </button>
      </section>

      <section className="mb-8 border border-slate-200 dark:border-slate-800 rounded-xl p-4">
        <h2 className="font-medium text-slate-800 dark:text-slate-200 mb-2">Notifications</h2>
        <Link
          href="/settings/notifications"
          className="text-sm text-amber-700 dark:text-amber-400 hover:text-amber-800 dark:hover:text-amber-300"
        >
          Notification preferences →
        </Link>
      </section>

      <section className="border border-red-200 dark:border-red-900/40 rounded-xl p-4 bg-red-50 dark:bg-red-950/10">
        <h2 className="font-medium text-red-700 dark:text-red-300 mb-2">Danger zone</h2>
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
          Download your data or permanently close your account.
        </p>
        <Link
          href="/settings/danger"
          className="text-sm text-red-700 dark:text-red-400 hover:text-red-300 font-medium"
        >
          Open danger zone →
        </Link>
      </section>
    </main>
  );
}
