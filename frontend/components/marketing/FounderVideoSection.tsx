"use client";

import {
  FOUNDER_VIDEO_DURATION_LABEL,
  FOUNDER_VIDEO_POSTER_SRC,
  FOUNDER_VIDEO_SRC,
} from "@/lib/marketing/founderVideo";

/**
 * Evergreen embedded player (return visitors + first-run visitors who scroll).
 * Never autoplays.
 */
export function FounderVideoSection() {
  return (
    <section
      className="max-w-3xl mx-auto px-6 pb-16"
      aria-labelledby="founder-video-heading"
    >
      <div
        className="rounded-2xl border border-amber-400/40 bg-black p-1 shadow-[0_0_48px_rgba(245,158,11,0.12)]"
      >
        <div className="rounded-xl bg-[radial-gradient(ellipse_at_center,rgba(245,158,11,0.12)_0%,#0a0a0a_70%)] p-2 sm:p-3">
          <h2
            id="founder-video-heading"
            className="text-center text-lg font-semibold text-amber-50 mb-3"
          >
            A note from Al ({FOUNDER_VIDEO_DURATION_LABEL})
          </h2>
          <video
            className="w-full rounded-lg bg-black aspect-video"
            src={FOUNDER_VIDEO_SRC}
            poster={FOUNDER_VIDEO_POSTER_SRC}
            playsInline
            controls
            preload="metadata"
          />
          <p className="mt-3 text-center text-xs text-amber-100/70 leading-relaxed max-w-lg mx-auto">
            Why FlintApply exists, how it&apos;s built, and what to expect — from
            the solo founder behind The Flint AI.
          </p>
        </div>
      </div>
    </section>
  );
}
