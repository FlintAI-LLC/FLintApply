"use client";

import { Zap } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  /** When omitted, no per-credit cost line is shown (e.g. active subscription). */
  costCredits?: number;
  pendingSuggestionCount: number;
  openAtsIssueCount: number;
  onConfirm: () => void;
  onCancel: () => void;
  onApplyImprovementsFirst?: () => void;
  applyImprovementsRunning?: boolean;
  disabled?: boolean;
  className?: string;
}

export function ReTailorFromScratchConfirm({
  costCredits,
  pendingSuggestionCount,
  openAtsIssueCount,
  onConfirm,
  onCancel,
  onApplyImprovementsFirst,
  applyImprovementsRunning = false,
  disabled = false,
  className,
}: Props) {
  const creditLabel =
    costCredits === 1 ? "credit" : costCredits != null ? "credits" : "";
  const unappliedCount = pendingSuggestionCount + openAtsIssueCount;

  return (
    <div
      className={cn(
        "w-full max-w-xl rounded-lg border border-amber-400/40 bg-amber-500/10 dark:bg-amber-400/10 p-4 space-y-3",
        className,
      )}
    >
      <div className="space-y-1">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          Re-tailor from scratch?
        </h3>
        <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
          Runs a new Phase 3 rewrite from your <strong>source resume</strong> and this job
          description. It does not apply pending chat highlights or unresolved ATS fixes for you.
        </p>
      </div>

      {costCredits != null && (
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/15 border border-amber-400/30 text-xs text-amber-800 dark:text-amber-200 w-fit">
          <Zap className="w-3.5 h-3.5 shrink-0" />
          Costs {costCredits} resume {creditLabel}
        </div>
      )}

      <ul className="text-xs text-slate-700 dark:text-slate-300 space-y-1 list-disc pl-4">
        <li>Your current tailored draft is replaced when the run succeeds.</li>
        <li>
          If the run fails or is hollow, your previous draft is restored and you may receive a
          credit refund per policy.
        </li>
        {unappliedCount > 0 && (
          <li>
            <strong>{unappliedCount}</strong> improvement
            {unappliedCount === 1 ? "" : "s"} still open (
            {pendingSuggestionCount > 0
              ? `${pendingSuggestionCount} pending suggestion${pendingSuggestionCount === 1 ? "" : "s"}`
              : null}
            {pendingSuggestionCount > 0 && openAtsIssueCount > 0 ? "; " : null}
            {openAtsIssueCount > 0
              ? `${openAtsIssueCount} open ATS item${openAtsIssueCount === 1 ? "" : "s"}`
              : null}
            ).
          </li>
        )}
        <li>A version snapshot of the current draft is saved before the run starts.</li>
      </ul>

      <div className="flex flex-wrap items-center gap-2 pt-1">
        <button
          type="button"
          onClick={onConfirm}
          disabled={disabled}
          className="px-3 py-1.5 rounded-lg bg-amber-400 text-slate-900 text-xs font-semibold hover:bg-amber-300 disabled:opacity-40"
        >
          Re-tailor from scratch
        </button>
        {onApplyImprovementsFirst && unappliedCount > 0 && (
          <button
            type="button"
            onClick={onApplyImprovementsFirst}
            disabled={disabled || applyImprovementsRunning}
            className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold disabled:opacity-40"
          >
            {applyImprovementsRunning ? "Applying…" : "Apply improvements first"}
          </button>
        )}
        <button
          type="button"
          onClick={onCancel}
          disabled={disabled}
          className="px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-400 dark:border-slate-600 text-xs text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 disabled:opacity-40"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
