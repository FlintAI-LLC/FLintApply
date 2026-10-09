import type { GuidanceStepId } from "@/lib/guidance/content";
import { isGuidanceSeen, isTutorialEnabled } from "@/lib/guidance/tutorial";

export function nextCoachGuidanceStep(ctx: {
  onModeSelector?: boolean;
  coachPanelOpened?: boolean;
  wholeStoryCoachVisible?: boolean;
}): GuidanceStepId | null {
  if (!isTutorialEnabled()) return null;
  if (ctx.onModeSelector && !isGuidanceSeen("coach.cc1")) return "coach.cc1";
  if (ctx.coachPanelOpened && !isGuidanceSeen("coach.cc2")) return "coach.cc2";
  if (ctx.wholeStoryCoachVisible && !isGuidanceSeen("coach.cc3")) return "coach.cc3";
  return null;
}
