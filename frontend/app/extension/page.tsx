"use client";

import Link from "next/link";
import { Loader2 } from "lucide-react";
import { useRequireAuth } from "@/lib/auth/guards";
import { extensionInstallHeadline } from "@/lib/extensionInstall";
import { ExtensionInstallGuide } from "@/components/extension/ExtensionInstallGuide";

export default function ExtensionInstallPage() {
  const { status } = useRequireAuth("/extension");

  if (status === "loading") {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-amber-700 dark:text-amber-400" />
      </div>
    );
  }

  return (
    <main className="max-w-2xl mx-auto px-4 py-8">
      <Link
        href="/dashboard"
        className="text-sm text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-300"
      >
        ← Back to dashboard
      </Link>
      <h1 className="text-2xl font-bold text-slate-900 dark:text-white mt-4 mb-2">
        {extensionInstallHeadline()}
      </h1>
      <p className="text-sm text-slate-600 dark:text-slate-400 mb-8">
        Use Chrome on job boards to capture postings, or skip straight to paste / in-app search below.
      </p>
      <ExtensionInstallGuide />
    </main>
  );
}
