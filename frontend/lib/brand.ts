/**
 * Canonical FlintApply branding — single source for user-facing product name.
 */

export const PRODUCT_NAME = "FlintApply" as const;

export const COMPANY_LINE = "by The Flint AI" as const;

export const COMPANY_NAME = "The Flint AI" as const;

export const LEGAL_CONTROLLER_NAME = "Alireza Barzin Zanganeh" as const;

export const LEGAL_OPERATOR_LINE =
  `${COMPANY_NAME} (${LEGAL_CONTROLLER_NAME})` as const;

export const COMPANY_URL = "https://theflintai.com" as const;

/** Separate desktop interview co-pilot — not part of FlintApply billing. */
export const FLINT_PRODUCT_NAME = "FlintGuide" as const;

export const FLINT_DESKTOP_URL = "https://guide.theflintai.com" as const;

export const FLINT_MARK_SRC = "/brand/flintguide-mark.png" as const;

/** When false, session export shows Coming soon instead of the handoff deep link. */
export const FLINT_HANDOFF_ENABLED = false as const;

export const PRIVACY_EMAIL = "privacy@flintapply.com" as const;

/** Bugs, product feedback, and general support (same inbox as privacy/DPO for v1). */
export const SUPPORT_EMAIL = "privacy@flintapply.com" as const;

/** Customized / enterprise plan inquiries from the public pricing grid. */
export const SALES_INQUIRY_EMAIL = "privacy@flintapply.com" as const;

/** FlintApply text wordmark PNGs — run `scripts/generate-flintapply-brand-assets.py` after art changes. */
export const WORDMARK_LIGHT_SRC = "/brand/flintapply-wordmark-light.png" as const;
/** Navy “Apply” letters lightened to brand blue for dark backgrounds (generated). */
export const WORDMARK_DARK_SRC = "/brand/flintapply-wordmark-dark.png" as const;

/** FlintApply square app icon (`mark.png` is the canonical path used by `BrandLogo`). */
export const FLINTAPPLY_ICON_SRC = "/brand/mark.png" as const;

/** The Flint AI company brand assets (umbrella org behind FlintApply). */
export const COMPANY_WORDMARK_SRC = "/brand/flint-ai-wordmark.png" as const;
export const COMPANY_LOCKUP_SRC = "/brand/flint-ai-lockup.png" as const;
export const COMPANY_ICON_SRC = "/brand/flint-ai-icon.png" as const;

/**
 * Framed product marketing shot — used by `ProductScreenshot` in inline
 * capability strips. Kept on the JPG because that shot is a crawler-friendly
 * flat render, not the atmospheric hero art.
 */
export const HERO_PRODUCT_SHOT_SRC = "/marketing/flintapply-hero.jpg" as const;

/**
 * Full-bleed pinned hero art. Dark 3D render of a document radiating into
 * hex nodes; transparent PNG so the wash underneath shines through the edges.
 * Kept separate from `HERO_PRODUCT_SHOT_SRC` because that constant is still
 * used by the plain framed screenshot and swapping it there would replace a
 * literal product screenshot with a stylised render.
 */
export const HERO_PRODUCT_SRC = "/marketing/hero-image.png" as const;

/** Session key — intro plays once per tab session. */
export const INTRO_SEEN_KEY = "flintapply:intro-seen";

export const INTRO_GREETING = {
  line: `Hi, I'm ${PRODUCT_NAME}.`,
  sub: "Your AI assistant for finding the jobs you actually fit and building the resume that gets you there.",
} as const;

export const METADATA_TITLE =
  `${PRODUCT_NAME} — AI resume tailoring, ATS optimization & job search` as const;

export const METADATA_DESCRIPTION =
  "Discover the job titles you actually fit, then tailor an ATS-optimized resume to every job description. Job search starts with tech employers; more industries are coming. Master resume, cover letters, application tracking in one place." as const;

/**
 * Job corpus scope — matches backend global seed (ATS-polled tech employers today).
 * Use these strings anywhere we describe in-app search so marketing stays honest.
 */
export const JOB_CORPUS_ROADMAP_NOTE =
  "We're starting with tech jobs and employers; other industries are planned in a later phase." as const;

/** Short label for filters, badges, and tight UI slots. */
export const JOB_CORPUS_SCOPE_LABEL = "Tech jobs (expanding soon)" as const;

/** One sentence for setup / jobs intro blocks. */
export const JOB_CORPUS_INTRO =
  `${PRODUCT_NAME} matches your story to real openings from our tech employer job corpus. ${JOB_CORPUS_ROADMAP_NOTE}` as const;

/** Shown on off-ramp when the query is outside the tech corpus. */
export const JOB_CORPUS_EARLY_ACCESS_NOTE =
  "In-app search is focused on tech roles for the first ~3 months; more industries are on the roadmap." as const;

export function linkedInJobSearchUrl(query: string): string {
  const q = encodeURIComponent(query.trim() || "jobs")
  return `https://www.linkedin.com/jobs/search/?keywords=${q}`
}

export function indeedJobSearchUrl(query: string): string {
  const q = encodeURIComponent(query.trim() || "jobs")
  return `https://www.indeed.com/jobs?q=${q}`
}

export const METADATA_OG_TITLE = PRODUCT_NAME;

export const METADATA_OG_DESCRIPTION =
  "Find the roles you fit, then tailor an ATS-optimized resume for each one." as const;

export function productScreenshotAlt(): string {
  return `${PRODUCT_NAME} — AI resume tailoring and ATS optimization, framed brand mockup`;
}

