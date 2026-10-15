import { AUTOFILL_BETA_EXPECTATION_APPLY_HELPER } from "@/lib/autofillBetaExpectations";
import { isAutofillAllowlistedUrl } from "@/lib/extensionAutofillAllowlist";

export type ApplyEmployerSiteState = "A" | "B" | "C" | "D";

export function sanitizeJobPostingUrl(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const trimmed = raw.trim();
  if (trimmed.length > 2048) return null;
  if ([...trimmed].some((ch) => ch.charCodeAt(0) < 32)) return null;
  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;
    if (!parsed.hostname) return null;
    if (parsed.username || parsed.password) return null;
    return parsed.href;
  } catch {
    return null;
  }
}

export type ApplyEmployerSiteStructural = "no-url" | "off-allowlist" | "allowlisted";

export function resolveApplyEmployerSiteStructural(
  jobPostingUrl: string | null | undefined,
): { structural: ApplyEmployerSiteStructural; href: string | null } {
  const safeUrl = sanitizeJobPostingUrl(jobPostingUrl);
  if (!safeUrl) {
    return { structural: "no-url", href: null };
  }
  if (!isAutofillAllowlistedUrl(safeUrl)) {
    return { structural: "off-allowlist", href: safeUrl };
  }
  return { structural: "allowlisted", href: safeUrl };
}

/** Query flag read by the extension popup to show apply/autofill UI instead of JD capture. */
export const FLINT_APPLY_EMPLOYER_INTENT_PARAM = "flintapply";
export const FLINT_APPLY_EMPLOYER_INTENT_VALUE = "apply";

export function withApplyOnEmployerSiteIntent(postingUrl: string): string {
  const parsed = new URL(postingUrl);
  parsed.searchParams.set(FLINT_APPLY_EMPLOYER_INTENT_PARAM, FLINT_APPLY_EMPLOYER_INTENT_VALUE);
  return parsed.href;
}

export function applyEmployerSiteNavigation(
  jobPostingUrl: string | null | undefined,
): { structural: ApplyEmployerSiteStructural; href: string | null } {
  const resolved = resolveApplyEmployerSiteStructural(jobPostingUrl);
  if (!resolved.href || resolved.structural !== "allowlisted") {
    return resolved;
  }
  return { structural: resolved.structural, href: withApplyOnEmployerSiteIntent(resolved.href) };
}

export function toDisplayState(
  structural: ApplyEmployerSiteStructural,
  extensionDetected: boolean | null,
): ApplyEmployerSiteState {
  if (structural === "no-url") return "D";
  if (structural === "off-allowlist") return "C";
  return extensionDetected === false ? "B" : "A";
}

export function applyEmployerSiteLabel(state: ApplyEmployerSiteState): string | null {
  if (state === "D") return null;
  if (state === "C") return "Open job posting";
  return "Apply on employer site";
}

export function applyEmployerSiteHelperCopy(options: {
  state: ApplyEmployerSiteState;
  extensionDetected: boolean | null;
}): string {
  const { state, extensionDetected } = options;
  if (state === "C") {
    const base =
      "This site is not on the autofill list yet. Open the posting and submit with your downloaded resume.";
    if (extensionDetected === false) {
      return base;
    }
    return base;
  }
  if (state === "A" || state === "B") {
    if (extensionDetected !== false) {
      return AUTOFILL_BETA_EXPECTATION_APPLY_HELPER;
    }
    return "Opens the posting. Install Flint Apply and sign in — autofill (beta) only helps with a few contact fields on some forms; you will still complete most of the application by hand.";
  }
  return "";
}

export function showGetExtensionLink(options: {
  state: ApplyEmployerSiteState;
  extensionDetected: boolean | null;
}): boolean {
  const { state, extensionDetected } = options;
  if (state === "D") return true;
  if (state === "B") return true;
  if (state === "C" && extensionDetected === false) return true;
  return false;
}
