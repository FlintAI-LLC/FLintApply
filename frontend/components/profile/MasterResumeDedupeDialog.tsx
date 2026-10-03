"use client";

import { AlertTriangle } from "lucide-react";

interface Props {
  open: boolean;
  busy?: boolean;
  liveChunkCount: number;
  onClose: () => void;
  onConfirm: () => void;
}

/** Confirms bulk dedupe of duplicate projects, education, and near-duplicate skills. */
export function MasterResumeDedupeDialog({
  open,
  busy = false,
  liveChunkCount,
  onClose,
  onConfirm,
}: Props) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="master-dedupe-title"
    >
      <div className="w-full max-w-md rounded-2xl border border-amber-500/40 bg-white dark:bg-slate-900 shadow-xl p-6 space-y-4">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div>
            <h2 id="master-dedupe-title" className="text-lg font-semibold text-slate-900 dark:text-white">
              Remove duplicate chunks?
            </h2>
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-2">
              We scan your <strong>{liveChunkCount}</strong> live chunk
              {liveChunkCount === 1 ? "" : "s"} and soft-delete extras when the same project or school
              appears more than once, or when skill lines are near-duplicates. We keep the richest version
              (more detail and dates when present). Experience bullets are not changed.
            </p>
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-2">
              You can still edit individual chunks afterward. This cannot be undone in one click, but
              deleted chunks disappear from tailoring only.
            </p>
          </div>
        </div>
        <div className="flex gap-3 pt-1">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="flex-1 py-2.5 border border-slate-300 dark:border-slate-700 rounded-xl text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="flex-1 py-2.5 bg-amber-400 hover:bg-amber-300 text-slate-900 font-semibold rounded-xl text-sm disabled:opacity-50"
          >
            {busy ? "Deduping…" : "Remove duplicates"}
          </button>
        </div>
      </div>
    </div>
  );
}
