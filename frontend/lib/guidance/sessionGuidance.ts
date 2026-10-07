import type { GuidanceStepId } from "@/lib/guidance/content";
import { isGuidanceSeen, isTutorialEnabled, markGuidanceSeen } from "@/lib/guidance/tutorial";

type SessionStepSuffix = "jt1" | "jt1b" | "jt2a" | "jt2b" | "jt2c" | "jt2d" | "jt3" | "jt4" | "jt5";

function sessionKey(sessionId: string, suffix: SessionStepSuffix): string {
  return `session.${sessionId}.${suffix}`;
}

export function markSessionGuidanceSeen(sessionId: string, step: GuidanceStepId): void {
  const suffix = step.replace("session.", "") as SessionStepSuffix;
  markGuidanceSeen(sessionKey(sessionId, suffix));
}

function sessionSeen(sessionId: string, suffix: SessionStepSuffix): boolean {
  return isGuidanceSeen(sessionKey(sessionId, suffix));
}

export function nextSessionGuidanceStep(ctx: {
  sessionId: string;
  step: "analysis" | "rewrite" | "export" | "other";
  isNewSession?: boolean;
  firstAtsScore?: boolean;
  applyAllJustFinished?: boolean;
  exportUnblocked?: boolean;
  continuingToExport?: boolean;
}): GuidanceStepId | null {
  if (!isTutorialEnabled()) return null;

  const sid = ctx.sessionId;

  if (ctx.isNewSession && !sessionSeen(sid, "jt1")) {
    return "session.jt1";
  }

  if (ctx.step === "analysis" && sessionSeen(sid, "jt1") && !sessionSeen(sid, "jt1b")) {
    return "session.jt1b";
  }

  if (ctx.step === "rewrite") {
    if (!sessionSeen(sid, "jt2a")) return "session.jt2a";
    if (!sessionSeen(sid, "jt2b")) return "session.jt2b";
    if (ctx.continuingToExport && !sessionSeen(sid, "jt2d")) {
      return "session.jt2d";
    }
  }

  if (ctx.firstAtsScore && !sessionSeen(sid, "jt3")) {
    return "session.jt3";
  }

  if (ctx.applyAllJustFinished && !sessionSeen(sid, "jt4")) {
    return "session.jt4";
  }

  if (ctx.exportUnblocked && !sessionSeen(sid, "jt5")) {
    return "session.jt5";
  }

  return null;
}
