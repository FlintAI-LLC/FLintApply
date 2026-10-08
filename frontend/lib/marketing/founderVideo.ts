/**
 * Founder intro video — first-run fullscreen + evergreen embedded section.
 *
 * Drop assets at:
 * - `public/marketing/founder-intro.mp4`
 * - `public/marketing/founder-intro-poster.jpg`
 */

import { INTRO_SEEN_KEY } from "@/lib/brand";
import { shouldPlayIntro } from "@/lib/marketing/intro";

/** Return visitors: intro + fullscreen video are skipped. */
export const FOUNDER_FIRST_RUN_COMPLETE_KEY =
  "flintapply:first-run-complete" as const;

export const FOUNDER_VIDEO_SRC = "/marketing/founder-intro.mp4" as const;
export const FOUNDER_VIDEO_POSTER_SRC =
  "/marketing/founder-intro-poster.jpg" as const;

/** Shown in UI; keep in sync with `founder-intro.mp4` runtime (~4:15). */
export const FOUNDER_VIDEO_DURATION_LABEL = "~4:15" as const;

export const INTRO_DISMISSED_EVENT = "flintapply:intro-dismissed" as const;

export function isFounderFirstRunComplete(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return (
      localStorage.getItem(FOUNDER_FIRST_RUN_COMPLETE_KEY) === "1"
    );
  } catch {
    return false;
  }
}

export function markFounderFirstRunComplete(): void {
  try {
    localStorage.setItem(FOUNDER_FIRST_RUN_COMPLETE_KEY, "1");
  } catch {
    // Private browsing — still dismiss overlay for this visit.
  }
}

/** Whether the brand intro animation will run on this load (client only). */
export function readIntroWillPlay(): boolean {
  if (typeof window === "undefined") return false;

  const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  const params = new URLSearchParams(window.location.search);
  const forceIntro = params.get("intro") === "1";

  if (isFounderFirstRunComplete() && !forceIntro) {
    return false;
  }

  let introSeenThisSession = false;
  try {
    introSeenThisSession =
      !forceIntro && sessionStorage.getItem(INTRO_SEEN_KEY) === "1";
  } catch {
    introSeenThisSession = false;
  }

  return shouldPlayIntro({
    prefersReducedMotion: motionQuery.matches,
    alreadyPlayed: introSeenThisSession,
  });
}

export function dispatchIntroDismissed(): void {
  window.dispatchEvent(new CustomEvent(INTRO_DISMISSED_EVENT));
}
