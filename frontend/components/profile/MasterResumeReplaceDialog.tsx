"use client";

import { AlertTriangle } from "lucide-react";

interface Props {
  open: boolean;
  busy?: boolean;
  actionLabel: string;
  chunkCount?: number;
  onClose: () => void;
  onConfirm: () => void;
}

/** Confirms adding upload/paste content to the indexed master resume (merge + dedupe). */
export function MasterResumeReplaceDialog({
  open,
  busy = false,
  actionLabel,
  chunkCount,
  onClose,
  onConfirm,
}: Props) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="master-replace-title"
    >
      <div className="w-full max-w-md rounded-2xl border border-amber-500/40 bg-white dark:bg-slate-900 shadow-xl p-6 space-y-4">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div>
            <h2 id="master-replace-title" className="text-lg font-semibold text-slate-900 dark:text-white">
              Add to your master resume?
            </h2>
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-2">
              {actionLabel} will <strong>merge</strong> new sections into your profile
              {chunkCount != null && chunkCount > 0 ? (
                <> (you have {chunkCount} live chunk{chunkCount === 1 ? "" : "s"} now)</>
              ) : null}
              . Duplicate bullets and skills are skipped. You can add up to five source uploads over time.
            </p>
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-2">
              To wipe everything and start over, use a full replace from profile settings later, or save again from Tell your story (that path replaces the whole master resume).
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
            Keep current resume
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="flex-1 py-2.5 bg-amber-400 hover:bg-amber-300 text-slate-900 font-semibold rounded-xl text-sm disabled:opacity-50"
          >
            Add to master resume
          </button>
        </div>
      </div>
    </div>
  );
}
