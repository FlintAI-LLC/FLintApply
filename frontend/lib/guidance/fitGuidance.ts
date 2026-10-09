import type { GuidanceStepId } from "@/lib/guidance/content";
import { isGuidanceSeen, isTutorialEnabled } from "@/lib/guidance/tutorial";

export function nextFitGuidanceStep(ctx: {
  pageTab: "analyze" | "history";
  hasResult: boolean;
}): GuidanceStepId | null {
  if (!isTutorialEnabled()) return null;
  if (ctx.pageTab === "analyze" && !isGuidanceSeen("fit.ft1")) return "fit.ft1";
  if (ctx.hasResult && isGuidanceSeen("fit.ft1") && !isGuidanceSeen("fit.ft2")) {
    return "fit.ft2";
  }
  if (
    (ctx.pageTab === "history" || ctx.hasResult) &&
    isGuidanceSeen("fit.ft2") &&
    !isGuidanceSeen("fit.ft3")
  ) {
    return "fit.ft3";
  }
  return null;
}
