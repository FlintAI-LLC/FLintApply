/**
 * Mirrors autofill-runner content_scripts.matches hosts in flint-extension
 * manifest.json (Greenhouse, Lever, Ashby, Workday, iCIMS, UKG, Jobright,
 * LinkedIn /jobs/*). Logic ported verbatim from flint-extension/src/autofillFlags.ts
 * `isAutofillHost`.
 */

export function isAutofillAllowlistedUrl(url: string | undefined): boolean {
  if (!url) return false;
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return false;
    const host = parsed.hostname.toLowerCase();
    const path = parsed.pathname;

    if (host === "greenhouse.io" || host.endsWith(".greenhouse.io")) return true;
    if (host === "lever.co" || host.endsWith(".lever.co")) return true;
    if (host === "ashbyhq.com" || host.endsWith(".ashbyhq.com")) return true;
    if (host === "myworkdayjobs.com" || host.endsWith(".myworkdayjobs.com")) return true;
    if (host === "icims.com" || host.endsWith(".icims.com")) return true;
    if (host === "ukg.net" || host.endsWith(".ukg.net")) return true;
    if (host === "jobright.ai" || host === "www.jobright.ai") return true;

    if (host === "linkedin.com" || host.endsWith(".linkedin.com")) {
      return path === "/jobs" || path.startsWith("/jobs/");
    }

    return false;
  } catch {
    return false;
  }
}
