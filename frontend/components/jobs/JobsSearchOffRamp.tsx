"use client"

import Link from "next/link"
import { ExternalLink, Sparkles } from "lucide-react"
import {
  JOB_CORPUS_EARLY_ACCESS_NOTE,
  JOB_CORPUS_ROADMAP_NOTE,
  JOB_CORPUS_SCOPE_LABEL,
  indeedJobSearchUrl,
  linkedInJobSearchUrl,
} from "@/lib/brand"

interface Props {
  reason: string
  query: string
  subscribed: boolean
  onSearchWider?: () => void
  preferredTitles?: string[]
}

export function JobsSearchOffRamp({
  reason,
  query,
  subscribed,
  onSearchWider,
  preferredTitles = [],
}: Props) {
  const searchQuery = query.trim() || preferredTitles[0] || "jobs"

  return (
    <div
      className="mb-8 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-6 space-y-5"
      data-testid="jobs-off-ramp"
    >
      <div>
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
          Three ways to find your next role
        </h2>
        <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
          {reason === "non_tech"
            ? `“${query.trim()}” looks outside our current ${JOB_CORPUS_SCOPE_LABEL.toLowerCase()} index.`
            : reason === "empty_results"
              ? "We don’t have in-app listings for this search yet."
              : "These results may not match what you meant — try the paths below."}
        </p>
      </div>

      <ol className="space-y-4 text-sm">
        <li className="rounded-lg border border-slate-100 dark:border-slate-800 p-4">
          <p className="font-medium text-slate-900 dark:text-white">
            1. Free tech corpus ({JOB_CORPUS_SCOPE_LABEL})
          </p>
          <p className="text-slate-600 dark:text-slate-400 mt-1">
            {JOB_CORPUS_EARLY_ACCESS_NOTE} {JOB_CORPUS_ROADMAP_NOTE}
          </p>
          {preferredTitles.length > 0 && (
            <p className="text-xs text-slate-500 dark:text-slate-500 mt-2">
              Try titles from your profile: {preferredTitles.slice(0, 3).join(", ")}
            </p>
          )}
        </li>

        <li className="rounded-lg border border-slate-100 dark:border-slate-800 p-4">
          <p className="font-medium text-slate-900 dark:text-white">
            2. Expanded in-app search (Premium)
          </p>
          <p className="text-slate-600 dark:text-slate-400 mt-1">
            Broader index inside {JOB_CORPUS_SCOPE_LABEL.split("(")[0].trim()} — not every industry or
            role type worldwide.
          </p>
          {subscribed ? (
            onSearchWider && (
              <button
                type="button"
                onClick={onSearchWider}
                className="mt-3 inline-flex items-center gap-2 text-sm font-medium text-amber-800 dark:text-amber-300 hover:underline"
                data-testid="jobs-off-ramp-expand"
              >
                <Sparkles className="w-4 h-4" />
                Search wider (uses expanded search)
              </button>
            )
          ) : (
            <Link
              href="/billing"
              className="mt-3 inline-flex text-sm font-medium text-amber-800 dark:text-amber-300 hover:underline"
            >
              Upgrade for expanded search
            </Link>
          )}
        </li>

        <li className="rounded-lg border border-slate-100 dark:border-slate-800 p-4">
          <p className="font-medium text-slate-900 dark:text-white">
            3. External boards + tailor here
          </p>
          <p className="text-slate-600 dark:text-slate-400 mt-1">
            Search LinkedIn or Indeed, then paste a job into a new tailoring session — or use the
            browser extension on the listing page.
          </p>
          <div className="mt-3 flex flex-wrap gap-3">
            <a
              href={linkedInJobSearchUrl(searchQuery)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-sm text-slate-700 dark:text-slate-300 hover:text-amber-800 dark:hover:text-amber-300"
            >
              LinkedIn <ExternalLink className="w-3.5 h-3.5" />
            </a>
            <a
              href={indeedJobSearchUrl(searchQuery)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-sm text-slate-700 dark:text-slate-300 hover:text-amber-800 dark:hover:text-amber-300"
            >
              Indeed <ExternalLink className="w-3.5 h-3.5" />
            </a>
            <Link
              href="/extension"
              className="text-sm text-slate-700 dark:text-slate-300 hover:text-amber-800 dark:hover:text-amber-300"
            >
              Extension setup
            </Link>
            <Link
              href="/session/new"
              className="text-sm text-slate-700 dark:text-slate-300 hover:text-amber-800 dark:hover:text-amber-300"
            >
              Tailor from JD
            </Link>
          </div>
        </li>
      </ol>
    </div>
  )
}
