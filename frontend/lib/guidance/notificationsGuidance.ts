import type { GuidanceStepId } from "@/lib/guidance/content";
import { isGuidanceSeen, isTutorialEnabled } from "@/lib/guidance/tutorial";

const CHAIN: GuidanceStepId[] = [
  "notifications.no1",
  "notifications.no2",
  "notifications.no3",
  "notifications.no4",
  "notifications.no5",
];

export function nextNotificationsGuidanceStep(): GuidanceStepId | null {
  if (!isTutorialEnabled()) return null;
  return CHAIN.find((id) => !isGuidanceSeen(id)) ?? null;
}
