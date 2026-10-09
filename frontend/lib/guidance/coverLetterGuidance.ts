import type { GuidanceStepId } from "@/lib/guidance/content";
import { isGuidanceSeen, isTutorialEnabled } from "@/lib/guidance/tutorial";

export function nextCoverLetterGuidanceStep(ctx: {
  hasRecentSessions: boolean;
  panelOpen: boolean;
}): GuidanceStepId | null {
  if (!isTutorialEnabled()) return null;
  if (!ctx.panelOpen && !isGuidanceSeen("cover_letter.cl1")) {
    return "cover_letter.cl1";
  }
  if (ctx.panelOpen) {
    if (!isGuidanceSeen("cover_letter.cl2")) return "cover_letter.cl2";
    if (isGuidanceSeen("cover_letter.cl2") && !isGuidanceSeen("cover_letter.cl3")) {
      return "cover_letter.cl3";
    }
  }
  return null;
}
