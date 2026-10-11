"use client"

import Link from "next/link"
import { FormEvent, useCallback, useEffect, useState } from "react"
import { GuidanceModal } from "@/components/guidance/GuidanceModal"
import { GUIDANCE_CONTENT } from "@/lib/guidance/content"
import { nextCareerWatchGuidanceStep } from "@/lib/guidance/careerWatchGuidance"
import { useGuidanceModal } from "@/lib/guidance/useGuidanceModal"
import { clsx } from "clsx"
import {
  AlertCircle,
  ArrowLeft,
  BellRing,
  Building2,
  ExternalLink,
  Loader2,
  Plus,
  Radar,
  Sparkles,
  Trash2,
} from "lucide-react"
import { useRequireAuth } from "@/lib/auth/guards"
import { bumpNotificationsRefresh } from "@/lib/notifications"
import {
  clearCareerWatchInAppNotifications,
  createCareerWatch,
  deleteCareerWatch,
  detectCareersPage,
  dismissCareerAlert,
  dismissCareerAlertsBulk,
  getCareerWatchKeywordSuggestions,
  getCareerWatchLimits,
  listCareerAlerts,
  listCareerWatches,
  type CareerWatchAlert,
  type CareerWatchEntry,
  type CareerWatchLimits,
} from "@/lib/careerWatch"

const inputClass =
  "w-full bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg px-3 py-2.5 text-sm text-slate-800 dark:text-slate-200 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-amber-400/80 focus:border-amber-400/50"

function companyInitial(name: string): string {
  const trimmed = name.trim()
  if (!trimmed) return "?"
  return trimmed.charAt(0).toUpperCase()
}

function atsLabel(ats: string): string {
  return ats.replace(/_/g, " ")
}

function matchScoreTone(score: number | null): string {
  if (score === null || Number.isNaN(score)) {
    return "bg-slate-200/80 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-300 dark:border-slate-600"
  }
  if (score >= 0.66) {
    return "bg-emerald-500/15 text-emerald-800 dark:text-emerald-300 border-emerald-500/35"
  }
  if (score >= 0.4) {
    return "bg-amber-500/15 text-amber-800 dark:text-amber-300 border-amber-500/35"
  }
  return "bg-sky-500/15 text-sky-800 dark:text-sky-300 border-sky-500/35"
}

export default function CareerWatchPage() {
  const { session, status } = useRequireAuth("/career-watch")
  const token = session?.backendAccessToken
  const [watches, setWatches] = useState<CareerWatchEntry[]>([])
  const [alerts, setAlerts] = useState<CareerWatchAlert[]>([])
  const [limits, setLimits] = useState<CareerWatchLimits | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [url, setUrl] = useState("")
  const [keywords, setKeywords] = useState("")
  const [companyName, setCompanyName] = useState("")
  const [detectedAts, setDetectedAts] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [suggestingKeywords, setSuggestingKeywords] = useState(false)
  const [keywordsFieldFocused, setKeywordsFieldFocused] = useState(false)
  const [selectedAlertIds, setSelectedAlertIds] = useState<Set<string>>(() => new Set())
  const [dismissingAlerts, setDismissingAlerts] = useState(false)
  const [clearingBell, setClearingBell] = useState(false)

  const pickCareerWatchGuidance = useCallback(
    () =>
      nextCareerWatchGuidanceStep({
        watchCount: watches.length,
        keywordsFieldFocused,
        alertCount: alerts.length,
      }),
    [watches.length, keywordsFieldFocused, alerts.length],
  )
  const { guidanceStep, onAcknowledge, refresh } = useGuidanceModal(pickCareerWatchGuidance)

  useEffect(() => {
    refresh()
  }, [watches.length, alerts.length, keywordsFieldFocused, refresh])

  const load = useCallback(async () => {
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      const [watchRows, alertRows, limitRows] = await Promise.all([
        listCareerWatches(token),
        listCareerAlerts(token),
        getCareerWatchLimits(token),
      ])
      setWatches(watchRows)
      setAlerts(alertRows)
      setSelectedAlertIds((prev) => {
        const valid = new Set(alertRows.map((a) => a.id))
        const next = new Set<string>()
        for (const id of prev) {
          if (valid.has(id)) next.add(id)
        }
        return next
      })
      setLimits(limitRows)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load Career Watch")
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    void load()
  }, [load])

  async function handleDetect() {
    if (!token || !url.trim()) return
    try {
      const result = await detectCareersPage(token, url.trim())
      setDetectedAts(result.ats_type)
      if (result.company_name && !companyName) {
        setCompanyName(result.company_name)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Detection failed")
    }
  }

  async function handleAdd(e: FormEvent) {
    e.preventDefault()
    if (!token || !url.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const kw = [
        ...new Set(
          keywords
            .split(",")
            .map((k) => k.trim())
            .filter(Boolean),
        ),
      ]
      await createCareerWatch(token, {
        careers_page_url: url.trim(),
        company_name: companyName.trim() || undefined,
        keywords: kw,
      })
      setUrl("")
      setKeywords("")
      setCompanyName("")
      setDetectedAts(null)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add company")
    } finally {
      setSubmitting(false)
    }
  }

  async function handleRemove(watchId: string) {
    if (!token) return
    await deleteCareerWatch(token, watchId)
    await load()
  }

  async function handleDismiss(alertId: string) {
    if (!token) return
    await dismissCareerAlert(token, alertId)
    await load()
    bumpNotificationsRefresh()
  }

  function toggleAlertSelected(alertId: string) {
    setSelectedAlertIds((prev) => {
      const next = new Set(prev)
      if (next.has(alertId)) next.delete(alertId)
      else next.add(alertId)
      return next
    })
  }

  const allAlertsSelected =
    alerts.length > 0 && alerts.every((a) => selectedAlertIds.has(a.id))

  function toggleSelectAllAlerts() {
    if (allAlertsSelected) {
      setSelectedAlertIds(new Set())
      return
    }
    setSelectedAlertIds(new Set(alerts.map((a) => a.id)))
  }

  async function handleDismissSelected() {
    if (!token || selectedAlertIds.size === 0) return
    setDismissingAlerts(true)
    setError(null)
    try {
      await dismissCareerAlertsBulk(token, {
        alert_ids: [...selectedAlertIds],
      })
      setSelectedAlertIds(new Set())
      await load()
      bumpNotificationsRefresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to dismiss alerts")
    } finally {
      setDismissingAlerts(false)
    }
  }

  async function handleDismissAllAlerts() {
    if (!token || alerts.length === 0) return
    setDismissingAlerts(true)
    setError(null)
    try {
      await dismissCareerAlertsBulk(token, { dismiss_all: true })
      setSelectedAlertIds(new Set())
      await load()
      bumpNotificationsRefresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to dismiss alerts")
    } finally {
      setDismissingAlerts(false)
    }
  }

  async function handleClearBellJobAlerts() {
    if (!token) return
    setClearingBell(true)
    setError(null)
    try {
      await clearCareerWatchInAppNotifications(token)
      bumpNotificationsRefresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not clear notification bell")
    } finally {
      setClearingBell(false)
    }
  }

  async function handleSuggestKeywords() {
    if (!token) return
    setSuggestingKeywords(true)
    setError(null)
    try {
      const suggested = await getCareerWatchKeywordSuggestions(token)
      if (suggested.length === 0) {
        setError("No keyword suggestions yet — add skills or experience to your master resume first.")
        return
      }
      const existing = keywords
        .split(",")
        .map((k) => k.trim().toLowerCase())
        .filter(Boolean)
      const merged = [...existing]
      for (const s of suggested) {
        const lower = s.toLowerCase()
        if (!merged.includes(lower)) {
          merged.push(lower)
        }
      }
      setKeywords(merged.join(", "))
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load keyword suggestions")
    } finally {
      setSuggestingKeywords(false)
    }
  }

  if (status === "loading" || loading) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center text-slate-600 dark:text-slate-400">
        <Loader2 className="w-6 h-6 animate-spin mr-2" />
        Loading Career Watch…
      </div>
    )
  }

  const watchPct =
    limits && limits.max_companies > 0
      ? Math.min(100, (limits.active_watches / limits.max_companies) * 100)
      : 0

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white">
      <div className="mx-auto max-w-4xl px-6 py-10 space-y-10">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-1.5 text-sm text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to dashboard
        </Link>

        <header
          className="relative overflow-hidden rounded-2xl border border-amber-400/25 bg-gradient-to-br from-amber-500/10 via-white to-violet-500/10 dark:from-amber-500/15 dark:via-slate-900 dark:to-violet-600/10 p-6 sm:p-8 shadow-sm"
        >
          <div
            className="pointer-events-none absolute -right-8 -top-8 h-40 w-40 rounded-full bg-amber-400/20 blur-3xl"
            aria-hidden
          />
          <div
            className="pointer-events-none absolute -left-6 bottom-0 h-32 w-32 rounded-full bg-violet-500/15 blur-3xl"
            aria-hidden
          />
          <div className="relative flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-2 rounded-full border border-amber-400/30 bg-amber-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-amber-800 dark:text-amber-300">
                <Radar className="h-3.5 w-3.5" />
                Live ATS monitoring
              </div>
              <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Career Watch</h1>
              <p className="max-w-xl text-sm text-slate-600 dark:text-slate-400">
                Track company career boards and get notified when new roles match your keywords — before
                they hit the big job sites.
              </p>
            </div>
            {limits && (
              <div className="flex flex-wrap gap-2 sm:max-w-xs sm:justify-end">
                <p className="sr-only" data-testid="career-watch-limits-summary">
                  {limits.active_watches} / {limits.max_companies} companies watched
                </p>
                <div className="rounded-xl border border-slate-200/80 dark:border-slate-700/80 bg-white/70 dark:bg-slate-950/50 px-4 py-3 text-sm backdrop-blur-sm min-w-[9rem]">
                  <p className="text-xs text-slate-500 dark:text-slate-400">Companies</p>
                  <p className="text-lg font-semibold tabular-nums">
                    {limits.active_watches}
                    <span className="text-slate-400 dark:text-slate-500 font-normal">
                      {" "}
                      / {limits.max_companies}
                    </span>
                  </p>
                  <div className="mt-2 h-1.5 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-amber-400 to-amber-600 transition-all"
                      style={{ width: `${watchPct}%` }}
                    />
                  </div>
                </div>
                <div className="rounded-xl border border-slate-200/80 dark:border-slate-700/80 bg-white/70 dark:bg-slate-950/50 px-4 py-3 text-sm backdrop-blur-sm">
                  <p className="text-xs text-slate-500 dark:text-slate-400">Poll cadence</p>
                  <p className="text-lg font-semibold tabular-nums">
                    {limits.poll_interval_minutes}
                    <span className="text-sm font-normal text-slate-500"> min</span>
                  </p>
                </div>
              </div>
            )}
          </div>
        </header>

        <div
          className="rounded-xl border border-violet-400/25 bg-violet-500/5 px-4 py-3 text-sm text-slate-700 dark:text-slate-300"
          data-testid="career-watch-referral-tip"
        >
          <span className="font-semibold text-violet-800 dark:text-violet-300">Referrals:</span>{" "}
          Add every company where you have a referral or inside contact — paste their official careers
          page URL so you see new roles early.{" "}
          <Link href="/guide" className="font-medium text-violet-700 dark:text-violet-400 hover:underline">
            More in the guide
          </Link>
        </div>

        {error && (
          <div
            className="flex items-start gap-2 rounded-xl border border-red-400/25 bg-red-400/10 px-4 py-3 text-sm text-red-800 dark:text-red-300"
            role="alert"
          >
            <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form
          onSubmit={handleAdd}
          className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-sm space-y-5"
        >
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-400/25">
              <Building2 className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">Add a company</h2>
              <p className="text-xs text-slate-600 dark:text-slate-400">
                Paste a Greenhouse, Lever, Ashby, or similar careers URL.
              </p>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-medium text-slate-600 dark:text-slate-400" htmlFor="cw-url">
              Careers page URL
            </label>
            <div className="flex flex-col gap-2 sm:flex-row">
              <input
                id="cw-url"
                className={clsx(inputClass, "flex-1")}
                placeholder="https://boards.greenhouse.io/acme"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onBlur={() => void handleDetect()}
              />
              <button
                type="button"
                className="shrink-0 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-4 py-2.5 text-sm font-medium text-slate-800 dark:text-slate-200 hover:border-amber-400/50 hover:bg-amber-500/5 transition-colors"
                onClick={() => void handleDetect()}
              >
                Detect ATS
              </button>
            </div>
            {detectedAts && (
              <p
                data-testid="career-watch-detected-ats"
                className="text-xs text-emerald-700 dark:text-emerald-400 flex items-center gap-1.5"
              >
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500" />
                Detected ATS:{" "}
                <span className="font-medium capitalize">{atsLabel(detectedAts)}</span>
              </p>
            )}
          </div>

          <div className="space-y-2">
            <label className="text-xs font-medium text-slate-600 dark:text-slate-400" htmlFor="cw-name">
              Company name (optional)
            </label>
            <input
              id="cw-name"
              className={inputClass}
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="Acme Corp"
            />
          </div>

          <div className="space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <label className="text-xs font-medium text-slate-600 dark:text-slate-400" htmlFor="cw-keywords">
                Keywords (comma-separated)
              </label>
              <button
                type="button"
                className="inline-flex items-center gap-1.5 rounded-lg border border-violet-400/30 bg-violet-500/10 px-2.5 py-1.5 text-xs font-semibold text-violet-800 dark:text-violet-300 hover:bg-violet-500/15 disabled:opacity-50 transition-colors"
                disabled={suggestingKeywords}
                onClick={() => void handleSuggestKeywords()}
              >
                {suggestingKeywords ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Sparkles className="h-3.5 w-3.5" />
                )}
                Suggest from master resume
              </button>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-500">
              Alerts need two keyword hits in the posting, or one hit in the job title.
            </p>
            <input
              id="cw-keywords"
              className={inputClass}
              placeholder="python, backend, remote"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              onFocus={() => setKeywordsFieldFocused(true)}
            />
          </div>

          <button
            type="submit"
            disabled={submitting || !url.trim()}
            data-testid="career-watch-add-submit"
            className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-amber-500 to-amber-600 px-5 py-2.5 text-sm font-semibold text-slate-950 shadow-sm hover:from-amber-400 hover:to-amber-500 disabled:opacity-50 transition-all"
          >
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Add watch
          </button>
        </form>

        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <Building2 className="h-5 w-5 text-amber-600 dark:text-amber-400" />
            <h2 className="text-lg font-semibold">Watched companies</h2>
          </div>
          {watches.length === 0 ? (
            <div
              className="rounded-2xl border border-dashed border-slate-300 dark:border-slate-700 bg-white/50 dark:bg-slate-900/40 px-6 py-12 text-center"
              data-testid="career-watch-empty"
            >
              <Radar className="mx-auto h-10 w-10 text-slate-400 dark:text-slate-600 mb-3" />
              <p className="text-sm font-medium text-slate-700 dark:text-slate-300">No companies watched yet</p>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-500 max-w-sm mx-auto">
                Add a careers URL above — we&apos;ll poll the board and ping you when keywords match.
              </p>
            </div>
          ) : (
            <ul className="space-y-3" data-testid="career-watch-list">
              {watches.map((watch) => (
                <li
                  key={watch.id}
                  data-testid={`career-watch-entry-${watch.id}`}
                  className="flex items-start justify-between gap-4 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm hover:border-amber-400/30 transition-colors"
                >
                  <div className="flex gap-3 min-w-0">
                    <div
                      className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400/25 to-violet-500/20 text-base font-bold text-amber-900 dark:text-amber-200 border border-amber-400/20"
                      aria-hidden
                    >
                      {companyInitial(watch.company_name)}
                    </div>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2 min-w-0">
                        <p className="font-semibold text-slate-900 dark:text-white truncate min-w-0 flex-1">
                          {watch.company_name}
                        </p>
                        <span
                          className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400"
                        >
                          {atsLabel(watch.ats_type)}
                        </span>
                      </div>
                      {watch.keywords.length > 0 && (
                        <div
                          className="mt-2 flex flex-wrap gap-1.5"
                          data-testid={`career-watch-keywords-${watch.id}`}
                        >
                          {watch.keywords.map((kw, i) => (
                            <span
                              key={`${kw}-${i}`}
                              className="text-[11px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-900 dark:text-amber-200 border border-amber-400/25"
                            >
                              {kw}
                            </span>
                          ))}
                        </div>
                      )}
                      <Link
                        href={watch.careers_page_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-amber-700 dark:text-amber-400 hover:text-amber-800 dark:hover:text-amber-300"
                      >
                        Careers page <ExternalLink className="h-3 w-3" />
                      </Link>
                    </div>
                  </div>
                  <button
                    type="button"
                    aria-label="Remove watch"
                    className="rounded-lg border border-slate-200 dark:border-slate-700 p-2 text-slate-500 hover:border-red-400/40 hover:bg-red-500/10 hover:text-red-600 dark:hover:text-red-400 transition-colors shrink-0"
                    onClick={() => void handleRemove(watch.id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="space-y-4 pb-8">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <BellRing className="h-5 w-5 text-violet-600 dark:text-violet-400" />
              <h2 className="text-lg font-semibold">Recent alerts</h2>
              {alerts.length > 0 && (
                <span className="text-xs font-semibold tabular-nums px-2 py-0.5 rounded-full bg-violet-500/15 text-violet-800 dark:text-violet-300 border border-violet-400/25">
                  {alerts.length}
                </span>
              )}
            </div>
            {alerts.length > 0 && (
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  data-testid="career-watch-dismiss-selected"
                  disabled={dismissingAlerts || selectedAlertIds.size === 0}
                  className="rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-1.5 text-xs font-medium disabled:opacity-50 hover:border-violet-400/40"
                  onClick={() => void handleDismissSelected()}
                >
                  {dismissingAlerts ? "Dismissing…" : `Dismiss selected (${selectedAlertIds.size})`}
                </button>
                <button
                  type="button"
                  data-testid="career-watch-dismiss-all"
                  disabled={dismissingAlerts}
                  className="rounded-lg border border-red-400/30 bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-800 dark:text-red-300 disabled:opacity-50 hover:bg-red-500/15"
                  onClick={() => void handleDismissAllAlerts()}
                >
                  Dismiss all
                </button>
              </div>
            )}
          </div>
          {alerts.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 dark:border-slate-700 bg-white/50 dark:bg-slate-900/40 px-6 py-10 text-center space-y-3">
              <BellRing className="mx-auto h-9 w-9 text-slate-400 dark:text-slate-600 mb-2" />
              <p className="text-sm text-slate-600 dark:text-slate-400">No matching roles yet.</p>
              <p className="mt-1 text-xs text-slate-500">When a posting matches, it will show up here.</p>
              <button
                type="button"
                data-testid="career-watch-clear-bell"
                disabled={clearingBell}
                className="text-xs font-medium text-violet-700 dark:text-violet-400 hover:underline disabled:opacity-50"
                onClick={() => void handleClearBellJobAlerts()}
              >
                {clearingBell
                  ? "Clearing…"
                  : "Bell still shows old job alerts? Clear them from the menu icon"}
              </button>
            </div>
          ) : (
            <ul className="space-y-3" data-testid="career-watch-alerts-list">
              <li className="flex items-center gap-3 px-1 text-xs text-slate-600 dark:text-slate-400">
                <input
                  type="checkbox"
                  id="cw-alerts-select-all"
                  data-testid="career-watch-alerts-select-all"
                  checked={allAlertsSelected}
                  onChange={toggleSelectAllAlerts}
                  className="h-4 w-4 rounded border-slate-300 text-amber-600 focus:ring-amber-400"
                />
                <label htmlFor="cw-alerts-select-all" className="cursor-pointer select-none">
                  Select all on this page
                </label>
              </li>
              {alerts.map((alert) => (
                <li
                  key={alert.id}
                  data-testid={`career-watch-alert-${alert.id}`}
                  className={clsx(
                    "flex items-start gap-3 rounded-2xl border p-4 shadow-sm",
                    selectedAlertIds.has(alert.id)
                      ? "border-violet-400/50 bg-violet-500/5 dark:bg-violet-500/10"
                      : "border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900",
                  )}
                >
                  <input
                    type="checkbox"
                    aria-label={`Select alert ${alert.job_title}`}
                    data-testid={`career-watch-alert-select-${alert.id}`}
                    checked={selectedAlertIds.has(alert.id)}
                    onChange={() => toggleAlertSelected(alert.id)}
                    className="mt-1 h-4 w-4 shrink-0 rounded border-slate-300 text-amber-600 focus:ring-amber-400"
                  />
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-semibold text-slate-900 dark:text-white">{alert.job_title}</p>
                      {alert.match_score != null && (
                        <span
                          className={clsx(
                            "text-[10px] font-bold tabular-nums px-2 py-0.5 rounded-full border",
                            matchScoreTone(alert.match_score),
                          )}
                        >
                          {Math.round(alert.match_score * 100)}% match
                        </span>
                      )}
                    </div>
                    {alert.job_location && (
                      <p className="text-sm text-slate-600 dark:text-slate-400">{alert.job_location}</p>
                    )}
                    {alert.match_reason && (
                      <p className="text-xs text-slate-500 dark:text-slate-500">{alert.match_reason}</p>
                    )}
                    {alert.apply_url && (
                      <Link
                        href={alert.apply_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs font-medium text-violet-700 dark:text-violet-400 hover:underline"
                      >
                        View role <ExternalLink className="h-3 w-3" />
                      </Link>
                    )}
                  </div>
                  <button
                    type="button"
                    className="shrink-0 text-xs font-medium text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 underline-offset-2 hover:underline"
                    onClick={() => void handleDismiss(alert.id)}
                  >
                    Dismiss
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <GuidanceModal
          open={guidanceStep !== null}
          content={guidanceStep ? GUIDANCE_CONTENT[guidanceStep] : null}
          onAcknowledge={onAcknowledge}
        />
      </div>
    </div>
  )
}
