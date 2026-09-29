"use client";

import Link from "next/link";
import { Download, ExternalLink, Plug, Sparkles } from "lucide-react";
import { PRODUCT_NAME } from "@/lib/brand";
import {
  chromeWebStoreUrl,
  extensionBetaDownloadUrl,
  extensionBetaSupportLine,
  extensionInstallMode,
} from "@/lib/extensionInstall";

const UNPACKED_STEPS = [
  "Download and unzip the extension folder (keep the folder — do not delete it after loading).",
  "In Chrome, open chrome://extensions and turn on Developer mode (top right).",
  "Click Load unpacked and select the unzipped folder (the one that contains manifest.json).",
  `Pin the ${PRODUCT_NAME} icon, click it on a job posting, and sign in with the same account you use here.`,
  "Use Capture job on Greenhouse, Lever, Ashby, LinkedIn, and similar pages — then Tailor in FlintApply opens this site with the description filled in.",
] as const;

export function ExtensionInstallGuide({ compact = false }: { compact?: boolean }) {
  const mode = extensionInstallMode();
  const storeUrl = chromeWebStoreUrl();
  const downloadUrl = extensionBetaDownloadUrl();

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

        <div className="flex flex-wrap gap-2">
          {mode === "store" && storeUrl && (
            <a
              href={storeUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-amber-400 hover:bg-amber-300 text-slate-900 font-semibold rounded-xl text-sm"
            >
              <ExternalLink className="w-4 h-4" />
              Add to Chrome
            </a>
          )}
          {mode === "download" && downloadUrl && (
            <a
              href={downloadUrl}
              download
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-amber-400 hover:bg-amber-300 text-slate-900 font-semibold rounded-xl text-sm"
            >
              <Download className="w-4 h-4" />
              Download extension (zip)
            </a>
          )}
          {mode === "beta-manual" && (
            <p className="text-sm text-slate-700 dark:text-slate-300 bg-white/80 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3">
              {extensionBetaSupportLine()}
            </p>
          )}
        </div>
      </div>

      {(mode === "download" || mode === "beta-manual") && (
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/80 p-5 space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
            Install in Chrome (private beta)
          </h2>
          <ol className="list-decimal list-inside space-y-2 text-sm text-slate-700 dark:text-slate-300">
            {UNPACKED_STEPS.map((step) => (
              <li key={step} className="leading-relaxed">
                {step}
              </li>
            ))}
          </ol>
        </div>
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
