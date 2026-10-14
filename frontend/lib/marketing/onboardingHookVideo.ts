/**
 * ~1 min product intro (Shotcut) — first-run fullscreen + onboarding welcome embed.
 *
 * Assets:
 * - `public/marketing/onboarding-hook.mp4`
 * - `public/marketing/onboarding-hook-poster.jpg`
 */

export const ONBOARDING_HOOK_VIDEO_SRC =
  "/marketing/onboarding-hook.mp4" as const;
export const ONBOARDING_HOOK_VIDEO_POSTER_SRC =
  "/marketing/onboarding-hook-poster.jpg" as const;

/** Keep in sync with `onboarding-hook.mp4` runtime (~58s). */
export const ONBOARDING_HOOK_VIDEO_DURATION_LABEL = "~1 min" as const;

export const ONBOARDING_HOOK_FULLSCREEN_CAPTION =
  `See how FlintApply works (${ONBOARDING_HOOK_VIDEO_DURATION_LABEL})` as const;
