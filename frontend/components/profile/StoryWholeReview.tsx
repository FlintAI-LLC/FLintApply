"use client";

import { useCallback, useState } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { dispatchCreditsExhausted } from "@/lib/offerPopup";
import { streamCoach } from "@/lib/story";
import { ExhaustionPaywall } from "@/components/billing/ExhaustionPaywall";
import { EmailVerificationCallout } from "@/components/auth/EmailVerificationCallout";

interface Props {
  segments: string[];
  token: string;
  storyBuildSessionId: string;
  coachSessionUnlocked: boolean;
  onCoachSessionUnlocked: () => void;
  disabled?: boolean;
}

export function StoryWholeReview({
  segments,
  token,
  storyBuildSessionId,
  coachSessionUnlocked,
  onCoachSessionUnlocked,
  disabled = false,
}: Props) {
  const [feedback, setFeedback] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [showPaywall, setShowPaywall] = useState(false);
  const [creditAccepted, setCreditAccepted] = useState(coachSessionUnlocked);

  const runReview = useCallback(async () => {
    setLoading(true);
    setError(null);
    setErrorCode(null);
    setFeedback(null);
    let accumulated = "";
    try {
      await streamCoach(
        "",
        [],
        token,
        (delta) => {
          accumulated += delta;
        },
        {
          sessionId: storyBuildSessionId,
          coachMode: "whole_story",
          segments,
        },
      );
      const text = accumulated.trim();
      if (!text) {
        setError("The coach returned an empty response. Please try again.");
        return;
      }
      setFeedback(text);
      if (!coachSessionUnlocked) {
        onCoachSessionUnlocked();
      }
    } catch (err: unknown) {
      const e = err as Error & { code?: string };
      if (e.code === "insufficient_credits") {
        setShowPaywall(true);
        dispatchCreditsExhausted();
        setError("You need at least 1 credit for story coach feedback.");
      } else if (e.code === "email_verification_required") {
        setErrorCode("email_verification_required");
      } else {
        setError(e.message ?? "Could not load coaching feedback.");
      }
    } finally {
      setLoading(false);
    }
  }, [
    segments,
    token,
    storyBuildSessionId,
    coachSessionUnlocked,
    onCoachSessionUnlocked,
  ]);

  if (!creditAccepted) {
    return (
      <div
        data-testid="whole-story-coach-disclosure"
        className="rounded-xl border border-indigo-500/30 bg-indigo-50 dark:bg-indigo-950/20 p-4 space-y-3 text-sm"
      >
        <div className="flex items-center gap-2 text-indigo-700 dark:text-indigo-300 font-semibold">
          <Sparkles className="w-4 h-4" />
          Story coach feedback
        </div>
        <p className="text-slate-700 dark:text-slate-300">
          Finished your segments? Get coaching feedback on what to add across your whole story.{" "}
          <span className="text-amber-700 dark:text-amber-400 font-medium">1 credit</span> per resume
          build (not per segment). Credit packs do not unlock per-segment coach — subscribe for that.
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setCreditAccepted(true)}
            className="flex-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-2 text-sm font-medium"
          >
            Continue
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid="whole-story-coach"
      className="rounded-xl border border-indigo-500/30 bg-indigo-50 dark:bg-indigo-950/20 p-4 space-y-3 text-sm"
    >
      <div className="flex items-center gap-2 text-indigo-700 dark:text-indigo-300 font-semibold">
        <Sparkles className="w-4 h-4" />
        Story coach feedback
      </div>
      <p className="text-slate-600 dark:text-slate-400 text-xs">
        One pass over all segments — bullets on what to add (metrics, dates, scope).{" "}
        <span className="font-medium text-amber-700 dark:text-amber-400">1 credit / build</span>
      </p>

      {feedback ? (
        <div
          data-testid="whole-story-coach-feedback"
          className="rounded-lg bg-white/70 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-700 px-3 py-2 text-sm whitespace-pre-wrap text-slate-800 dark:text-slate-200"
        >
          {feedback}
        </div>
      ) : null}

      {errorCode === "email_verification_required" && <EmailVerificationCallout />}
      {error && (
        <p className="text-red-700 dark:text-red-400 text-xs">{error}</p>
      )}

      {showPaywall && (
        <ExhaustionPaywall
          token={token}
          compact
          contextMessage="You need credits for story coach feedback"
          onCreditsRefreshed={() => {
            setShowPaywall(false);
            setError(null);
          }}
        />
      )}

      <button
        type="button"
        data-testid="whole-story-coach-run"
        disabled={disabled || loading || Boolean(feedback)}
        onClick={() => void runReview()}
        className="w-full rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-3 py-2 text-sm font-semibold flex items-center justify-center gap-2"
      >
        {loading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Analyzing your story…
          </>
        ) : feedback ? (
          "Feedback ready"
        ) : (
          "Get coaching feedback"
        )}
      </button>
      {error && !loading && (
        <button
          type="button"
          onClick={() => void runReview()}
          className="w-full text-xs text-indigo-700 dark:text-indigo-300 hover:underline"
        >
          Retry
        </button>
      )}
    </div>
  );
}
