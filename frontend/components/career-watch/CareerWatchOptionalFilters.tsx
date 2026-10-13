"use client"

import { clsx } from "clsx"
import { ChevronDown } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { CAREER_WATCH_SENIORITY_LEVELS } from "@/lib/careerWatch"

type CareerWatchOptionalFiltersProps = {
  seniorityLevels: string[]
  onSeniorityChange: (levels: string[]) => void
  onAddRemote: () => void
}

function senioritySummaryLabel(selected: string[]): string {
  if (selected.length === 0) return "Any job level"
  const labels = CAREER_WATCH_SENIORITY_LEVELS.filter((l) => selected.includes(l.id)).map(
    (l) => l.label,
  )
  if (labels.length <= 2) return labels.join(", ")
  return `${labels.slice(0, 2).join(", ")} +${labels.length - 2}`
}

export function CareerWatchOptionalFilters({
  seniorityLevels,
  onSeniorityChange,
  onAddRemote,
}: CareerWatchOptionalFiltersProps) {
  const [levelMenuOpen, setLevelMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!levelMenuOpen) return
    function onPointerDown(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setLevelMenuOpen(false)
      }
    }
    document.addEventListener("mousedown", onPointerDown)
    return () => document.removeEventListener("mousedown", onPointerDown)
  }, [levelMenuOpen])

  function toggleLevel(id: string) {
    onSeniorityChange(
      seniorityLevels.includes(id)
        ? seniorityLevels.filter((x) => x !== id)
        : [...seniorityLevels, id],
    )
  }

  return (
    <div className="rounded-lg border border-slate-200/80 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-950/40 px-3 py-3 space-y-3">
      <p className="text-xs font-medium text-slate-600 dark:text-slate-400">
        Optional filters (narrow alerts)
      </p>

      <div className="flex flex-col sm:flex-row sm:flex-wrap gap-4 sm:items-end">
        <div className="space-y-1.5 min-w-[10rem]">
          <span className="text-xs font-medium text-slate-600 dark:text-slate-400">Remote</span>
          <button
            type="button"
            data-testid="career-watch-add-remote-keyword"
            className="inline-flex items-center gap-1.5 rounded-lg border border-sky-400/30 bg-sky-500/10 px-3 py-2 text-xs font-semibold text-sky-900 dark:text-sky-200 hover:bg-sky-500/15 transition-colors"
            onClick={onAddRemote}
          >
            + Add &quot;remote&quot; keyword
          </button>
          <p className="text-[11px] text-slate-500 dark:text-slate-500 leading-snug">
            Adds remote to your keyword list (same matching rules as other keywords).
          </p>
        </div>

        <div className="space-y-1.5 min-w-[12rem] flex-1 sm:max-w-xs" ref={menuRef}>
          <span
            id="career-watch-job-level-label"
            className="text-xs font-medium text-slate-600 dark:text-slate-400"
          >
            Job level
          </span>
          <div className="relative">
            <button
              type="button"
              data-testid="career-watch-seniority-menu"
              aria-haspopup="listbox"
              aria-expanded={levelMenuOpen}
              aria-labelledby="career-watch-job-level-label"
              className={clsx(
                "w-full inline-flex items-center justify-between gap-2 rounded-lg border px-3 py-2 text-xs font-medium transition-colors",
                seniorityLevels.length > 0
                  ? "border-amber-400/50 bg-amber-500/10 text-amber-950 dark:text-amber-100"
                  : "border-slate-300/60 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 hover:border-amber-400/40",
              )}
              onClick={() => setLevelMenuOpen((o) => !o)}
            >
              <span className="truncate text-left">{senioritySummaryLabel(seniorityLevels)}</span>
              <ChevronDown
                className={clsx("h-4 w-4 shrink-0 opacity-70 transition-transform", levelMenuOpen && "rotate-180")}
              />
            </button>
            {levelMenuOpen && (
              <ul
                role="listbox"
                aria-labelledby="career-watch-job-level-label"
                aria-multiselectable="true"
                className="absolute z-20 mt-1 w-full max-h-56 overflow-y-auto rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-lg py-1"
              >
                {CAREER_WATCH_SENIORITY_LEVELS.map((level) => {
                  const checked = seniorityLevels.includes(level.id)
                  return (
                    <li key={level.id} role="option" aria-selected={checked}>
                      <label
                        className="flex items-center gap-2 px-3 py-2 text-xs cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-800"
                      >
                        <input
                          type="checkbox"
                          data-testid={`career-watch-seniority-${level.id}`}
                          checked={checked}
                          onChange={() => toggleLevel(level.id)}
                          className="rounded border-slate-400 dark:border-slate-600"
                        />
                        <span className="text-slate-800 dark:text-slate-200">{level.label}</span>
                      </label>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
          <p className="text-[11px] text-slate-500 dark:text-slate-500 leading-snug">
            {seniorityLevels.length > 0
              ? "Only job titles that match a selected level."
              : "Leave as any level to skip title seniority filtering."}
          </p>
        </div>
      </div>
    </div>
  )
}
