import type { GuidanceStepId } from "@/lib/guidance/content";
import { isGuidanceSeen, isTutorialEnabled } from "@/lib/guidance/tutorial";

export function nextCareerWatchGuidanceStep(ctx: {
  watchCount: number;
  keywordsFieldFocused?: boolean;
  alertCount: number;
}): GuidanceStepId | null {
  if (!isTutorialEnabled()) return null;

  if (ctx.watchCount === 0 && !isGuidanceSeen("career_watch.cw1")) {
    return "career_watch.cw1";
  }
  if (
    ctx.watchCount === 0 &&
    isGuidanceSeen("career_watch.cw1") &&
    !isGuidanceSeen("career_watch.cw6")
  ) {
    return "career_watch.cw6";
  }
  if (ctx.keywordsFieldFocused) {
    if (isGuidanceSeen("career_watch.cw1") && !isGuidanceSeen("career_watch.cw2")) {
      return "career_watch.cw2";
    }
    if (isGuidanceSeen("career_watch.cw2") && !isGuidanceSeen("career_watch.cw3")) {
      return "career_watch.cw3";
    }
  }
  if (ctx.alertCount > 0 && isGuidanceSeen("career_watch.cw3")) {
    if (!isGuidanceSeen("career_watch.cw4")) return "career_watch.cw4";
    if (!isGuidanceSeen("career_watch.cw5")) return "career_watch.cw5";
  }
  return null;
}
