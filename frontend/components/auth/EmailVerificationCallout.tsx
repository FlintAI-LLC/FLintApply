"use client";

import Link from "next/link";

interface Props {
  compact?: boolean;
  className?: string;
}

/** Shown when AI features require a verified inbox — links to Settings. */
export function EmailVerificationCallout({ compact = false, className = "" }: Props) {
  return (
    <div
      className={
        className ||
        "text-red-700 dark:text-red-400 text-xs rounded-lg bg-red-50 dark:bg-red-950/20 border border-red-500/20 px-3 py-2 space-y-2"
      }
    >
      <p>
        Verify your email before using AI features.
        {!compact && " Check your inbox for the link we sent when you signed up."}
      </p>
      <p>
        <Link
          href="/settings#email-verification"
          className="font-medium text-amber-800 dark:text-amber-300 underline underline-offset-2 hover:text-amber-900 dark:hover:text-amber-200"
        >
          Open Settings to resend your verification email →
        </Link>
      </p>
    </div>
  );
}
