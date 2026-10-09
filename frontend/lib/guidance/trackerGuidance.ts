import type { GuidanceStepId } from "@/lib/guidance/content";
import { isGuidanceSeen, isTutorialEnabled } from "@/lib/guidance/tutorial";

export function nextTrackerGuidanceStep(ctx: {
  ready: boolean;
  formOpen?: boolean;
  duplicateWarningShown?: boolean;
}): GuidanceStepId | null {
  if (!isTutorialEnabled() || !ctx.ready) return null;
  if (!isGuidanceSeen("tracker.tr1")) return "tracker.tr1";
  if (ctx.formOpen && isGuidanceSeen("tracker.tr1") && !isGuidanceSeen("tracker.tr2")) {
    return "tracker.tr2";
  }
  if (ctx.duplicateWarningShown && !isGuidanceSeen("tracker.tr3")) {
    return "tracker.tr3";
  }
  if (isGuidanceSeen("tracker.tr1") && !isGuidanceSeen("tracker.tr4")) {
    return "tracker.tr4";
  }
  return null;
}
