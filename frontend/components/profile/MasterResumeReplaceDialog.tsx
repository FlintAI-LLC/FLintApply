"use client";

import { AlertTriangle } from "lucide-react";

interface Props {
  open: boolean;
  actionLabel: string;
  chunkCount?: number;
  onClose: () => void;
  onConfirm: () => void;
}

/** Confirms full replace of the stored master resume (upload, paste, or story save). */
export function MasterResumeReplaceDialog({
  open,
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
              Replace your master resume?
            </h2>
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-2">
              FlintApply keeps <strong>one</strong> master resume per account.{" "}
              {actionLabel} will <strong>delete</strong> your current indexed content
              {chunkCount != null && chunkCount > 0 ? (
                <> ({chunkCount} live chunk{chunkCount === 1 ? "" : "s"})</>
              ) : null}{" "}
              and replace it with the new version. This cannot be undone — story drafts in your browser are separate, but saved profile data is replaced.
            </p>
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-2">
              If you already spent credits on Tell your story, uploading a file replaces that work on your profile (credits are not refunded).
            </p>
          </div>
        </div>
        <div className="flex gap-3 pt-1">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 py-2.5 border border-slate-300 dark:border-slate-700 rounded-xl text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            Keep current resume
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="flex-1 py-2.5 bg-amber-400 hover:bg-amber-300 text-slate-900 font-semibold rounded-xl text-sm"
          >
            Replace master resume
          </button>
        </div>
      </div>
    </div>
  );
}
