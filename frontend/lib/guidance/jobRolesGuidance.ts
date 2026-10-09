import type { GuidanceStepId } from "@/lib/guidance/content";
import { isGuidanceSeen, isTutorialEnabled } from "@/lib/guidance/tutorial";

export function nextJobRolesGuidanceStep(): GuidanceStepId | null {
  if (!isTutorialEnabled()) return null;
  if (!isGuidanceSeen("job_roles.jr1")) return "job_roles.jr1";
  if (!isGuidanceSeen("job_roles.jr2")) return "job_roles.jr2";
  return null;
}
