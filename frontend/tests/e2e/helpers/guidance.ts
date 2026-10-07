import type { Page } from "@playwright/test"

/** Must match `TUTORIAL_ENABLED_KEY` in `lib/guidance/tutorial.ts`. */
const TUTORIAL_ENABLED_KEY = "flintapply.tutorial_enabled"

/**
 * Disable tutorial pop-ups before navigation. The guidance modal is a fixed
 * overlay that intercepts pointer events and breaks jobs/search E2E flows.
 */
export async function suppressTutorial(page: Page): Promise<void> {
  await page.addInitScript((key) => {
    try {
      localStorage.setItem(key, "false")
    } catch {
      // Storage unavailable in some contexts; tests may dismiss the modal manually.
    }
  }, TUTORIAL_ENABLED_KEY)
}
