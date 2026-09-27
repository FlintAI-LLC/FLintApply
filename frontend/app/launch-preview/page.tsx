"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import {
  formatLaunchDatePacific,
  launchAtFromEnv,
} from "@/lib/launch";

export default function LaunchPreviewPage() {
  const launchAt = launchAtFromEnv(process.env.NEXT_PUBLIC_LAUNCH_AT);
  const launchLabel = launchAt
    ? formatLaunchDatePacific(launchAt)
    : "Thursday, October 1, 2026 at 9:00 AM PDT";
  const router = useRouter();
  const searchParams = useSearchParams();
  const showError = searchParams.get("error") === "1";
  const [key, setKey] = useState("");
  const [message, setMessage] = useState<string | null>(
    showError ? "That code didn’t work. Try again or use your invite link." : null,
  );
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setMessage(null);
    try {
      const res = await fetch("/api/launch-preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key }),
      });
      if (!res.ok) {
        setMessage("Invalid early-access code.");
        return;
      }
      router.push("/auth?mode=register");
      router.refresh();
    } catch {
      setMessage("Something went wrong. Please try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-[60vh] max-w-md flex-col justify-center px-6 py-16">
      <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">
        Early access
      </h1>
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
        FlintApply opens to the public on {launchLabel}. Enter your invite
        code to sign in before then.
      </p>
      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">
          Invite code
          <input
            type="password"
            autoComplete="off"
            required
            value={key}
            onChange={(e) => setKey(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-white"
          />
        </label>
        {message ? (
          <p className="text-sm text-amber-800 dark:text-amber-200" role="alert">
            {message}
          </p>
        ) : null}
        <button
          type="submit"
          disabled={pending}
          className="w-full rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60 dark:bg-sky-600 dark:hover:bg-sky-500"
        >
          {pending ? "Checking…" : "Continue"}
        </button>
      </form>
      <Link
        href="/"
        className="mt-6 text-center text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400"
      >
        Back to home
      </Link>
    </main>
  );
}
