"use client";

import { CreditChargeConfirm } from "@/components/billing/CreditChargeConfirm";
import { cn } from "@/lib/utils";

export type AtsScoreRefreshMode = "current" | "stale_free" | "paid_confirm";

interface Props {
  mode: AtsScoreRefreshMode;
  busy?: boolean;
  disabled?: boolean;
  onRefreshFree: () => void;
  onRequestFullReanalysis: () => void;
  onConfirmFullReanalysis: () => void;
  onCancelFullReanalysis: () => void;
  className?: string;
}

export function AtsScoreRefreshControls({
  mode,
  busy = false,
  disabled = false,
  onRefreshFree,
  onRequestFullReanalysis,
  onConfirmFullReanalysis,
  onCancelFullReanalysis,
  className,
}: Props) {
  const blocked = disabled || busy;

  return (
    <div className={cn("flex flex-col items-end gap-2", className)}>
      {mode === "paid_confirm" ? (
        <CreditChargeConfirm
          actionLabel="Full AI re-analysis"
          onConfirm={onConfirmFullReanalysis}
          onCancel={onCancelFullReanalysis}
          disabled={blocked}
        />
      ) : mode === "stale_free" ? (
        <button
          type="button"
          onClick={onRefreshFree}
          disabled={blocked}
          className="px-4 py-2 rounded-lg bg-amber-400 text-slate-900 text-sm font-semibold hover:bg-amber-300 disabled:opacity-40"
        >
          {busy ? "Recalculating…" : "Recalculate ATS score"}
        </button>
      ) : (
        <button
          type="button"
          disabled
          className="px-4 py-2 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-600 text-sm font-semibold text-slate-500 dark:text-slate-400 cursor-not-allowed"
          title="Your score already matches this resume. Edit the resume or run a full re-analysis below."
        >
          No change in ATS score
        </button>
      )}

      {mode !== "paid_confirm" && (
        <button
          type="button"
          onClick={onRequestFullReanalysis}
          disabled={blocked}
          className="text-xs font-semibold text-slate-700 dark:text-slate-300 underline-offset-2 hover:underline disabled:opacity-40"
        >
          Full AI re-analysis (1 credit)
        </button>
      )}
      {mode === "current" && (
        <p className="text-[11px] text-slate-500 dark:text-slate-400 max-w-xs text-right">
          Score matches your resume. Use full re-analysis only for fresh AI issue text or new apply-all
          batches.
        </p>
      )}
      {mode === "stale_free" && (
        <p className="text-[11px] text-slate-500 dark:text-slate-400 max-w-xs text-right">
          Free refresh — no credit. Updates the number only.
        </p>
      )}
    </div>
  );
}

export function deriveAtsScoreRefreshMode(args: {
  staleSince: string | null | undefined;
  pendingPaidConfirm: boolean;
}): AtsScoreRefreshMode {
  if (args.pendingPaidConfirm) return "paid_confirm";
  if (args.staleSince) return "stale_free";
  return "current";
}
