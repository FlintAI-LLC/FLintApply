import type { GuidanceStepId } from "@/lib/guidance/content";
import { isGuidanceSeen, isTutorialEnabled } from "@/lib/guidance/tutorial";

export const MASTER_RESUME_CHUNK_GOAL = 100;

export function nextMasterResumeGuidanceStep(ctx: {
  liveCount: number;
  ingestJustFinished?: boolean;
  onBricksPage?: boolean;
  dedupeAvailable?: boolean;
  bricksReviewComplete?: boolean;
}): GuidanceStepId | null {
  if (!isTutorialEnabled()) return null;

  const { liveCount } = ctx;

  if (ctx.ingestJustFinished && !isGuidanceSeen("master_resume.mr1")) {
    return "master_resume.mr1";
  }

  if (
    liveCount >= 2 &&
    isGuidanceSeen("master_resume.mr1") &&
    !isGuidanceSeen("master_resume.mr2") &&
    ctx.dedupeAvailable
  ) {
    return "master_resume.mr2";
  }

  if (
    liveCount >= MASTER_RESUME_CHUNK_GOAL &&
    isGuidanceSeen("master_resume.mr1") &&
    !isGuidanceSeen("master_resume.mr3") &&
    (isGuidanceSeen("master_resume.mr2") || liveCount >= MASTER_RESUME_CHUNK_GOAL)
  ) {
    return "master_resume.mr3";
  }

  if (
    ctx.onBricksPage &&
    isGuidanceSeen("master_resume.mr3") &&
    !isGuidanceSeen("master_resume.mr4")
  ) {
    return "master_resume.mr4";
  }

  if (
    ctx.bricksReviewComplete &&
    liveCount >= MASTER_RESUME_CHUNK_GOAL &&
    isGuidanceSeen("master_resume.mr4") &&
    !isGuidanceSeen("master_resume.mr5")
  ) {
    return "master_resume.mr5";
  }

  return null;
}
