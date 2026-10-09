import type { GuidanceStepId } from "@/lib/guidance/content";
import { isGuidanceSeen, isTutorialEnabled } from "@/lib/guidance/tutorial";

const CHAIN: GuidanceStepId[] = ["extension.ex1", "extension.ex2", "extension.ex3"];

export function nextExtensionGuidanceStep(): GuidanceStepId | null {
  if (!isTutorialEnabled()) return null;
  return CHAIN.find((id) => !isGuidanceSeen(id)) ?? null;
}
