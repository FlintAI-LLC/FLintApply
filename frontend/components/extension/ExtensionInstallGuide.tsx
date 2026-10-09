"use client";

import Link from "next/link";
import { Download, ExternalLink, Plug, Sparkles } from "lucide-react";
import { PRODUCT_NAME } from "@/lib/brand";
import {
  chromeWebStoreExtensionVersion,
  chromeWebStoreUrl,
  extensionBetaDownloadUrl,
  extensionBetaSupportLine,
  extensionBetaVersion,
} from "@/lib/extensionInstall";

const UNPACKED_STEPS = [
  "Download and unzip the extension folder (keep the folder — do not delete it after loading).",
  "In Chrome, open chrome://extensions and turn on Developer mode (top right).",
  "Click Load unpacked and select the unzipped folder (the one that contains manifest.json).",
  `Pin the ${PRODUCT_NAME} icon, click it on a job posting, and sign in with the same account you use here.`,
  "Use Capture job on Greenhouse, Lever, Ashby, LinkedIn, and similar pages — then Tailor in FlintApply opens this site with the description filled in.",
] as const;

export function ExtensionInstallGuide({ compact = false }: { compact?: boolean }) {
  const storeUrl = chromeWebStoreUrl();
  const downloadUrl = extensionBetaDownloadUrl();
  const storeVersion = chromeWebStoreExtensionVersion();
  const betaVersion = extensionBetaVersion();
  const showBeta = Boolean(downloadUrl);
  const showStore = Boolean(storeUrl);
  const storeIsPrimary = showStore && !showBeta;

  return (
    <div className={compact ? "space-y-4" : "space-y-8"}>
      <div className="rounded-2xl border border-amber-400/30 bg-amber-500/5 dark:bg-amber-400/5 p-5 space-y-4">
        <div className="flex items-start gap-3">
          <Plug className="w-5 h-5 text-amber-700 dark:text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-2 min-w-0">
            <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
              Capture full job descriptions from employer career sites in one click, send them
              into {PRODUCT_NAME} for tailoring, and autofill applications from your tailored
              resume (beta on supported ATS forms).
            </p>
            {!compact && (
              <p className="text-xs text-slate-600 dark:text-slate-400">
                You do not need the extension to use {PRODUCT_NAME} — you can paste a job
                description or save postings from in-app job search instead.
              </p>
            )}
          </div>
        </div>
      </div>

      {showStore && (
        <div
          className={
            storeIsPrimary
              ? "rounded-2xl border border-amber-400/40 bg-amber-500/10 dark:bg-amber-400/5 p-5 space-y-3"
              : "rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/80 p-5 space-y-3"
          }
        >
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-800 dark:text-amber-300">
              {storeIsPrimary ? "Recommended" : "Easiest install"}
            </p>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white mt-1">
              Chrome Web Store
              {storeVersion ? ` (v${storeVersion})` : ""}
            </h2>
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-2 leading-relaxed">
              {storeIsPrimary
                ? "Official listing with one-click install and automatic updates. Sign in with the same account you use on flintapply.com."
                : "One-click install with automatic updates. Use this if you prefer not to use Developer mode."}
            </p>
          </div>
          <a
            href={storeUrl!}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-amber-400 hover:bg-amber-300 text-slate-900 font-semibold rounded-xl text-sm"
          >
            <ExternalLink className="w-4 h-4" />
            Add to Chrome
          </a>
        </div>
      )}

      {showBeta && (
        <div className="rounded-2xl border border-emerald-500/35 bg-emerald-50/80 dark:bg-emerald-950/25 p-5 space-y-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-emerald-800 dark:text-emerald-300">
              Private beta (developer mode)
            </p>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white mt-1">
              Latest build
              {betaVersion ? ` (v${betaVersion})` : ""}
            </h2>
            <p className="text-sm text-slate-700 dark:text-slate-300 mt-2 leading-relaxed">
              For pre-release capture and autofill fixes, install the beta zip in Chrome Developer
              mode. The Chrome Web Store build updates automatically but may lag by a release or
              two{storeVersion ? ` (Store is v${storeVersion} today)` : ""}.
            </p>
          </div>
          <a
            href={downloadUrl!}
            download
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-xl text-sm"
          >
            <Download className="w-4 h-4" />
            Download beta extension (zip)
          </a>
          <ol className="list-decimal list-inside space-y-2 text-sm text-slate-700 dark:text-slate-300">
            {UNPACKED_STEPS.map((step) => (
              <li key={step} className="leading-relaxed">
                {step}
              </li>
            ))}
          </ol>
        </div>
      )}

      {!showBeta && !showStore && (
        <p className="text-sm text-slate-700 dark:text-slate-300 bg-white/80 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3">
          {extensionBetaSupportLine()}
        </p>
      )}

      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-900/40 p-5 space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400 flex items-center gap-2">
          <Sparkles className="w-4 h-4" />
          Without the extension
        </h2>
        <ul className="space-y-2 text-sm">
          <li>
            <Link href="/session/new" className="text-amber-800 dark:text-amber-300 font-medium hover:underline">
              Paste a job description
            </Link>
            <span className="text-slate-600 dark:text-slate-400"> — start tailoring in the wizard.</span>
          </li>
          <li>
            <Link href="/jobs" className="text-amber-800 dark:text-amber-300 font-medium hover:underline">
              Search jobs in {PRODUCT_NAME}
            </Link>
            <span className="text-slate-600 dark:text-slate-400"> — save a posting from our corpus, then tailor.</span>
          </li>
          <li>
            <Link href="/dashboard" className="text-amber-800 dark:text-amber-300 font-medium hover:underline">
              Back to dashboard
            </Link>
            <span className="text-slate-600 dark:text-slate-400"> — follow the step list for your next action.</span>
          </li>
        </ul>
      </div>
    </div>
  );
}
