import type { Page } from "@playwright/test"

/** Must match `INTRO_SEEN_KEY` in `lib/brand.ts`. */
const INTRO_SEEN_KEY = "flintapply:intro-seen"

/** Must match `FOUNDER_FIRST_RUN_COMPLETE_KEY` in `lib/marketing/founderVideo.ts`. */
const FOUNDER_FIRST_RUN_COMPLETE_KEY = "flintapply:first-run-complete"

/**
 * Mark the landing intro as already played, before any page script runs.
 *
 * The intro is a full-viewport `position: fixed` overlay at z-index 100 that
 * swallows pointer events for its whole duration. Specs that drive the page
 * with `page.mouse.move` — which performs no actionability check, unlike
 * `locator.hover()` — otherwise land the cursor on the overlay instead of the
 * element under test, and the interaction silently never registers.
 *
 * Call before `page.goto`.
 */
export async function suppressIntro(page: Page): Promise<void> {
  await page.addInitScript(
    ({ introKey, firstRunKey }: { introKey: string; firstRunKey: string }) => {
      try {
        sessionStorage.setItem(introKey, "1")
        localStorage.setItem(firstRunKey, "1")
      } catch {
        // Storage can be unavailable; the intro stays dismissable by other means.
      }
    },
    {
      introKey: INTRO_SEEN_KEY,
      firstRunKey: FOUNDER_FIRST_RUN_COMPLETE_KEY,
    },
  )
}
