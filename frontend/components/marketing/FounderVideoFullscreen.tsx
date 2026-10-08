"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  FOUNDER_VIDEO_DURATION_LABEL,
  FOUNDER_VIDEO_POSTER_SRC,
  FOUNDER_VIDEO_SRC,
} from "@/lib/marketing/founderVideo";
import { INTRO_SCROLL_LOCK_CLASS } from "@/lib/marketing/intro";

interface Props {
  onDismiss: () => void;
}

/**
 * First-run only: cinematic fullscreen with autoplay (muted fallback) + Skip.
 */
export function FounderVideoFullscreen({ onDismiss }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [needsUnmute, setNeedsUnmute] = useState(false);
  const [fading, setFading] = useState(false);

  const dismiss = useCallback(() => {
    if (fading) return;
    setFading(true);
    const video = videoRef.current;
    if (video) {
      video.pause();
    }
    window.setTimeout(() => {
      onDismiss();
    }, 280);
  }, [fading, onDismiss]);

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
    document.documentElement.classList.add(INTRO_SCROLL_LOCK_CLASS);

    const video = videoRef.current;
    if (!video) return;

    const tryPlay = async () => {
      try {
        video.muted = false;
        await video.play();
        setNeedsUnmute(false);
      } catch {
        try {
          video.muted = true;
          await video.play();
          setNeedsUnmute(true);
        } catch {
          setNeedsUnmute(true);
        }
      }
    };

    void tryPlay();

    return () => {
      document.documentElement.classList.remove(INTRO_SCROLL_LOCK_CLASS);
    };
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") dismiss();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [dismiss]);

  const unmute = () => {
    const video = videoRef.current;
    if (!video) return;
    video.muted = false;
    void video.play();
    setNeedsUnmute(false);
  };

  return (
    <div
      className={`fixed inset-0 z-[101] flex items-center justify-center bg-black transition-opacity duration-300 motion-reduce:transition-none ${
        fading ? "pointer-events-none opacity-0" : "opacity-100"
      }`}
      role="dialog"
      aria-modal="true"
      aria-label="A note from the founder"
    >
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(245,158,11,0.22)_0%,rgba(0,0,0,0.92)_55%,#000_100%)]"
        aria-hidden
      />

      <button
        type="button"
        onClick={dismiss}
        className="absolute top-6 right-6 z-20 rounded-lg border border-amber-200/30 bg-slate-950/80 px-4 py-2 text-sm font-medium text-amber-50 hover:bg-slate-900/90 transition-colors"
      >
        Skip video
      </button>

      <div className="relative z-10 w-full max-w-4xl px-4 sm:px-6">
        <div
          className="rounded-xl border border-amber-400/45 bg-black/60 p-1 shadow-[0_0_80px_rgba(245,158,11,0.15)]"
        >
          <video
            ref={videoRef}
            className="w-full rounded-lg bg-black aspect-video"
            src={FOUNDER_VIDEO_SRC}
            poster={FOUNDER_VIDEO_POSTER_SRC}
            playsInline
            controls
            preload="auto"
            onEnded={dismiss}
          />
        </div>
        <p className="mt-3 text-center text-sm text-amber-100/80">
          A note from Al ({FOUNDER_VIDEO_DURATION_LABEL})
        </p>
        {needsUnmute ? (
          <div className="mt-3 flex justify-center">
            <button
              type="button"
              onClick={unmute}
              className="rounded-lg border border-amber-300/40 bg-amber-500/15 px-4 py-2 text-sm font-medium text-amber-50 hover:bg-amber-500/25"
            >
              Tap to turn on sound
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
