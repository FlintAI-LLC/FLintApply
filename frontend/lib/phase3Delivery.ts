import type { TailoredResumeOutput } from "@/lib/api";

export const KEPT_PRIOR_NOTE =
  "Regenerate discarded incomplete model output; your previous tailored resume was kept.";
export const CREDIT_RETURNED_NOTE = " Credit returned.";

export function findKeptPriorNote(notes: readonly string[]): string | null {
  return notes.find((n) => n.startsWith(KEPT_PRIOR_NOTE)) ?? null;
}

export interface Phase3DoneInput {
  output: TailoredResumeOutput;
  priorKept?: boolean;
  /** True only when the server confirmed it returned this run's credit. */
  creditRefunded?: boolean;
  /** Tailored resume that was on screen when the regenerate started. */
  priorSnapshot: TailoredResumeOutput | null;
}

export interface Phase3DeliveryResolution {
  tailored: TailoredResumeOutput;
  /** True when the client had to bring back the snapshot itself. */
  restoredFromSnapshot: boolean;
}

function countBullets(resume: TailoredResumeOutput | null): number {
  return (resume?.experience ?? []).reduce((sum, e) => sum + (e.bullets?.length ?? 0), 0);
}

export function hasUsableSkills(resume: TailoredResumeOutput | null): boolean {
  return (resume?.skills ?? []).some((s) => s.trim().length > 0);
}

function withNote(resume: TailoredResumeOutput, note: string): TailoredResumeOutput {
  const notes = (resume.rewrite_notes ?? []).filter((n) => !n.startsWith(KEPT_PRIOR_NOTE));
  return { ...resume, rewrite_notes: [...notes, note] };
}

/**
 * The server keeps the previous resume when a rerun degrades. This is the
 * client-side backstop: if the server could not (no stored prior) but the
 * browser still holds the resume the user had, that resume wins over a rebuilt
 * tree, and Skills is never left empty when the snapshot had skills.
 */
export function resolvePhase3Delivery(input: Phase3DoneInput): Phase3DeliveryResolution {
  const { output, priorKept, creditRefunded, priorSnapshot } = input;
  if (priorKept) {
    return { tailored: output, restoredFromSnapshot: false };
  }

  const degraded =
    output.phase3_delivery === "deterministic_fallback" ||
    (hasUsableSkills(priorSnapshot) && !hasUsableSkills(output));
  if (!degraded || countBullets(priorSnapshot) === 0 || priorSnapshot === null) {
    return { tailored: output, restoredFromSnapshot: false };
  }

  const note = KEPT_PRIOR_NOTE + (creditRefunded === true ? CREDIT_RETURNED_NOTE : "");
  return {
    tailored: withNote({ ...priorSnapshot, phase3_delivery: "llm" }, note),
    restoredFromSnapshot: true,
  };
}
