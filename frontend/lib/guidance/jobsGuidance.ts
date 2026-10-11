import type { GuidanceStepId } from "@/lib/guidance/content";
import { isGuidanceSeen, isTutorialEnabled } from "@/lib/guidance/tutorial";

export function nextJobsGuidanceStep(ctx: {
  onPreferencesPage?: boolean;
  beforeFirstSearch?: boolean;
  searchResultCount?: number;
  offRampShown?: boolean;
  firstBookmark?: boolean;
}): GuidanceStepId | null {
  if (!isTutorialEnabled()) return null;

  if (ctx.onPreferencesPage && !isGuidanceSeen("jobs.js5")) {
    return "jobs.js5";
  }

  if (ctx.beforeFirstSearch && !isGuidanceSeen("jobs.js1")) {
    return "jobs.js1";
  }

  if (
    ctx.searchResultCount !== undefined &&
    ctx.searchResultCount > 0 &&
    isGuidanceSeen("jobs.js1") &&
    !isGuidanceSeen("jobs.js6")
  ) {
    return "jobs.js6";
  }

  if (
    ctx.searchResultCount !== undefined &&
    ctx.searchResultCount > 0 &&
    isGuidanceSeen("jobs.js1") &&
    !isGuidanceSeen("jobs.js2")
  ) {
    return "jobs.js2";
  }

  if (
    (ctx.offRampShown || ctx.searchResultCount === 0) &&
    isGuidanceSeen("jobs.js1") &&
    !isGuidanceSeen("jobs.js3")
  ) {
    return "jobs.js3";
  }

  if (ctx.firstBookmark && isGuidanceSeen("jobs.js2") && !isGuidanceSeen("jobs.js4")) {
    return "jobs.js4";
  }

  return null;
}
