"use client";

import { cn } from "@/lib/utils";

interface Props {
  usedUsd: number;
  capUsd: number;
  label?: string;
  compact?: boolean;
  className?: string;
}

export function AiBudgetMeter({
  usedUsd,
  capUsd,
  label = "Platform AI allowance",
  compact = false,
  className,
}: Props) {
  const safeCap = Math.max(capUsd, 0.01);
  const used = Math.min(safeCap, Math.max(0, usedUsd));
  const pct = Math.min(100, Math.round((used / safeCap) * 100));
  const warn = pct >= 80;

  return (
    <div className={cn("min-w-0", className)}>
      <div
        className={cn(
          "flex justify-between text-xs text-slate-600 dark:text-slate-400",
          compact ? "mb-0.5" : "mb-1",
        )}
      >
        <span className="truncate">{label}</span>
        <span className="tabular-nums shrink-0 ml-2">
          ${used.toFixed(2)} / ${safeCap.toFixed(2)}
          {!compact && <span className="text-slate-500 dark:text-slate-500 ml-1">({pct}%)</span>}
        </span>
      </div>
      <div
        className={cn(
          "h-1.5 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden",
          compact && "h-1",
        )}
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={cn(
            "h-full rounded-full transition-all",
            warn ? "bg-amber-500" : "bg-slate-500 dark:bg-slate-400",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      {warn && !compact && (
        <p className="mt-1 text-[11px] text-amber-700 dark:text-amber-300">
          Most of your free AI allowance is used. Chat and apply-all may stop until you upgrade.
        </p>
      )}
    </div>
  );
}
