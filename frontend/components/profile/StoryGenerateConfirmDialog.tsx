"use client";

import { AlertTriangle, Loader2, Sparkles } from "lucide-react";

export type StoryGenerateConfirmVariant =
  | "first_generate"
  | "regenerate"
  | "back_to_segments";

interface Props {
  open: boolean;
  variant: StoryGenerateConfirmVariant;
  segmentCount: number;
  creditLabel: string;
  submitting?: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export function StoryGenerateConfirmDialog({
  open,
  variant,
  segmentCount,
  creditLabel,
  submitting = false,
  onClose,
  onConfirm,
}: Props) {
  if (!open) return null;

  const title =
    variant === "back_to_segments"
      ? "Add more to your story?"
      : variant === "regenerate"
        ? "Generate again?"
        : "Ready to generate your resume?";

  const body =
    variant === "back_to_segments" ? (
      <>
        You can record or edit segments without using a credit. If you generate a new draft after
        adding more, that counts as a new generate ({creditLabel}).
      </>
    ) : (
      <>
        <p>
          You have <strong>{segmentCount}</strong> segment{segmentCount === 1 ? "" : "s"} recorded.
          Only continue if you&apos;ve said everything you want in your story — jobs, skills,
          wins, education, and gaps you care about.
        </p>
        <p className="mt-2">
          {variant === "first_generate" ? (
            <>
              This first generate is <strong>free</strong>. If you go back to add segments and
              generate again, that second generate costs <strong>1 credit</strong>.
            </>
          ) : (
            <>
              This generate costs <strong>{creditLabel}</strong>. Add every segment you want{" "}
              <em>before</em> you generate so you don&apos;t pay again to revise your story.
            </>
          )}
        </p>
      </>
    );

  const confirmLabel =
    variant === "back_to_segments"
      ? "Yes, add more segments"
      : variant === "regenerate"
        ? "Generate again"
        : "Yes, generate now";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="story-generate-title"
    >
      <div className="w-full max-w-md rounded-2xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-xl p-6 space-y-4">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div>
            <h2 id="story-generate-title" className="text-lg font-semibold text-slate-900 dark:text-white">
              {title}
            </h2>
            <div className="text-sm text-slate-600 dark:text-slate-400 mt-2 space-y-2">{body}</div>
          </div>
        </div>

        {variant !== "back_to_segments" && (
          <div className="rounded-lg bg-slate-100 dark:bg-slate-800 px-3 py-2 text-sm text-slate-700 dark:text-slate-300">
            Cost for this generate: <strong>{creditLabel}</strong>
          </div>
        )}

        <div className="flex gap-3 pt-1">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="flex-1 py-2.5 border border-slate-300 dark:border-slate-700 rounded-xl text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50"
          >
            {variant === "back_to_segments" ? "Stay on review" : "Not yet — keep recording"}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={submitting}
            className="flex-1 py-2.5 bg-amber-400 hover:bg-amber-300 text-slate-900 font-semibold rounded-xl text-sm flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {submitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Working…
              </>
            ) : (
              <>
                {variant !== "back_to_segments" && <Sparkles className="w-4 h-4" />}
                {confirmLabel}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
