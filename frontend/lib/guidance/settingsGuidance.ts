import type { GuidanceStepId } from "@/lib/guidance/content";
import { isGuidanceSeen, isTutorialEnabled } from "@/lib/guidance/tutorial";

export function nextSettingsGuidanceStep(): GuidanceStepId | null {
  if (!isTutorialEnabled()) return null;
  if (!isGuidanceSeen("settings.se1")) return "settings.se1";
  return null;
}
