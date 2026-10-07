"use client";

import Link from "next/link";
import type { GuidanceContent } from "@/lib/guidance/content";

interface Props {
  content: GuidanceContent | null;
  open: boolean;
  onAcknowledge: () => void;
}

export function GuidanceModal({ content, open, onAcknowledge }: Props) {
  if (!open || !content) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="guidance-modal-title"
    >
      <div className="w-full max-w-md rounded-2xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-xl p-6 space-y-4">
        <div>
          <h2 id="guidance-modal-title" className="text-lg font-semibold text-slate-900 dark:text-white">
            {content.title}
          </h2>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-2 leading-relaxed">{content.body}</p>
        </div>
        {content.learnMoreHref ? (
          <Link
            href={content.learnMoreHref}
            className="text-sm font-medium text-amber-800 dark:text-amber-300 hover:underline"
            onClick={onAcknowledge}
          >
            {content.learnMoreLabel ?? "Learn more"} →
          </Link>
        ) : null}
        <button
          type="button"
          onClick={onAcknowledge}
          className="w-full rounded-xl bg-amber-400 hover:bg-amber-300 text-slate-900 font-semibold text-sm py-2.5 transition-colors"
        >
          OK
        </button>
      </div>
    </div>
  );
}
