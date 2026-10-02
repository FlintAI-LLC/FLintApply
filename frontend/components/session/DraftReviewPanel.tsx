"use client";

import { useCallback, useEffect, useState } from "react";
import {
  deleteDraftBullet,
  getDraftReview,
  type DraftReviewPayload,
  ApiError,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { AlertCircle, Loader2, Trash2 } from "lucide-react";

interface Props {
  sessionId: string;
  enabled: boolean;
  onSessionDraftChanged?: () => void;
}

export function DraftReviewPanel({
  sessionId,
  enabled,
  onSessionDraftChanged,
}: Props) {
  const [data, setData] = useState<DraftReviewPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [noDraftYet, setNoDraftYet] = useState(false);

  const load = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    setNoDraftYet(false);
    try {
      const review = await getDraftReview(sessionId);
      setData(review);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setNoDraftYet(true);
        setError(null);
        setData(null);
      } else {
        const msg =
          e instanceof ApiError ? e.message : "Could not load draft review.";
        setError(msg);
        setData(null);
      }
    } finally {
      setLoading(false);
    }
  }, [enabled, sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleDelete = async (bulletId: string) => {
    setDeletingId(bulletId);
    setError(null);
    try {
      const review = await deleteDraftBullet(sessionId, bulletId);
      setData(review);
      onSessionDraftChanged?.();
    } catch (e) {
      const msg =
        e instanceof ApiError ? e.message : "Could not remove bullet.";
      setError(msg);
    } finally {
      setDeletingId(null);
    }
  };

  if (!enabled) return null;

  if (loading && !data) {
    return (
      <div
        data-testid="draft-review-loading"
        className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 py-4"
      >
        <Loader2 className="w-4 h-4 animate-spin" />
        Loading draft review…
      </div>
    );
  }

  if (noDraftYet) {
    return (
      <p
        data-testid="draft-review-empty"
        className="text-sm text-slate-600 dark:text-slate-400 border border-dashed border-slate-300 dark:border-slate-600 rounded-lg px-3 py-3 mb-6"
      >
        Draft review will appear after you run tailored rewrite (Phase 3).
      </p>
    );
  }

  if (error && !data) {
    return (
      <p
        data-testid="draft-review-error"
        className="text-sm text-amber-800 dark:text-amber-200 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-lg px-3 py-2"
      >
        {error}
      </p>
    );
  }

  if (!data) return null;

  const { keyword_coverage: kw, length_estimate: len, duplicate_candidates: dups } =
    data;

  return (
    <section
      data-testid="draft-review-panel"
      className="mb-6 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50/80 dark:bg-slate-900/40 p-4 space-y-4"
      aria-label="Draft review"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          Draft review
        </h2>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="text-xs text-amber-700 dark:text-amber-300 hover:underline disabled:opacity-50"
        >
          Refresh
        </button>
      </div>

      {error && (
        <p className="text-xs text-red-700 dark:text-red-300 flex items-center gap-1">
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
          {error}
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2 text-xs">
        <div className="rounded-lg border border-slate-200 dark:border-slate-600 p-3">
          <p className="font-medium text-slate-800 dark:text-slate-200 mb-1">
            Keyword coverage
          </p>
          {kw.missing.length === 0 ? (
            <p className="text-green-700 dark:text-green-400">
              All must-have keywords covered.
            </p>
          ) : (
            <p className="text-slate-600 dark:text-slate-400">
              Missing: {kw.missing.join(", ")}
            </p>
          )}
        </div>
        <div className="rounded-lg border border-slate-200 dark:border-slate-600 p-3">
          <p className="font-medium text-slate-800 dark:text-slate-200 mb-1">
            Length estimate
          </p>
          <p
            className={cn(
              len.within_target
                ? "text-green-700 dark:text-green-400"
                : "text-amber-800 dark:text-amber-200",
            )}
          >
            ~{len.pages.toFixed(1)} page{len.pages === 1 ? "" : "s"}
            {!len.within_target && " (over target)"}
          </p>
        </div>
      </div>

      {dups.length > 0 && (
        <div className="rounded-lg border border-amber-300/50 dark:border-amber-700/50 bg-amber-50/50 dark:bg-amber-950/20 p-3">
          <p className="text-xs font-medium text-amber-900 dark:text-amber-100 mb-2">
            Possible duplicate bullets
          </p>
          <ul className="space-y-1 text-xs text-slate-700 dark:text-slate-300">
            {dups.map((d) => (
              <li key={`${d.bullet_id_a}-${d.bullet_id_b}`}>
                {d.bullet_id_a} ↔ {d.bullet_id_b} (
                {(d.similarity * 100).toFixed(0)}% similar)
              </li>
            ))}
          </ul>
        </div>
      )}

      <ul className="space-y-2 max-h-64 overflow-y-auto">
        {data.bullets.map((b) => (
          <li
            key={b.id}
            className="flex gap-2 items-start rounded-lg border border-slate-200 dark:border-slate-600 p-2 text-sm"
          >
            <div className="flex-1 min-w-0">
              <p className="text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">
                {b.section} · {b.id}
              </p>
              <p className="text-slate-800 dark:text-slate-200">{b.text}</p>
              {b.lint_issues.length > 0 && (
                <ul className="mt-1 space-y-0.5">
                  {b.lint_issues.map((issue, i) => (
                    <li
                      key={`${issue.rule}-${i}`}
                      className="text-xs text-amber-800 dark:text-amber-200"
                    >
                      {issue.rule}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <button
              type="button"
              title="Remove from draft (keeps master bricks)"
              disabled={deletingId === b.id}
              onClick={() => void handleDelete(b.id)}
              className="shrink-0 p-1.5 rounded-md text-slate-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30 disabled:opacity-40"
            >
              {deletingId === b.id ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Trash2 className="w-4 h-4" />
              )}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
