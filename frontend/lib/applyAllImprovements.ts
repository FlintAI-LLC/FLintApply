import {
  buildBatchChatMessage,
  enrichIssuesWithInferredAnchors,
  hydratePatchesFromIssues,
  issueAnchorKey,
  sourceIssueKeysForPatches,
} from "@/lib/anchoredPatch";
import { applyResumePatch, normalizeResumePatch } from "@/lib/applyResumePatch";
import type { BlockingIssue, QAOutput, ResumePatch, TailoredResumeOutput } from "@/lib/api";
import { dedupeBlockingIssues } from "@/components/session/ATSGuidancePanel";
import { issueKey } from "@/lib/issueAnchors";
import { canApplyMechanicalQuickWin, tryApplyMechanicalQuickWin } from "@/lib/mechanicalFix";
import { isPatchPlaceable } from "@/lib/suggestionHighlight";

/** Matches backend `MAX_CHAT_TARGET_ISSUES` in app/agent/chat.py */
export const MAX_CHAT_TARGET_ISSUES = 8;

/** Batch apply-all rounds allowed per ATS score (resets after manual Recalculate ATS). */
export const MAX_APPLY_ALL_ROUNDS = 1;

export function applyAllRoundsRemaining(roundsUsed: number): number {
  return Math.max(0, MAX_APPLY_ALL_ROUNDS - roundsUsed);
}

export function isApplyAllRoundLimitReached(roundsUsed: number): boolean {
  return roundsUsed >= MAX_APPLY_ALL_ROUNDS;
}

export type OpenImprovementSelection = {
  /** All open blocking + quick-win issues (deduped blocking, not skipped or addressed). */
  issues: BlockingIssue[];
  blockingCount: number;
  quickWinCount: number;
};

export function selectOpenImprovementIssues(
  qa: QAOutput | null | undefined,
  addressedKeys: ReadonlySet<string>,
  skippedKeys: ReadonlySet<string>,
): OpenImprovementSelection {
  if (!qa || qa.ats_score === undefined) {
    return { issues: [], blockingCount: 0, quickWinCount: 0 };
  }

  const blockingOpen = dedupeBlockingIssues(qa.blocking_issues ?? []).filter(
    (issue) => !skippedKeys.has(issueKey(issue)) && !addressedKeys.has(issueKey(issue)),
  );
  const quickWinsOpen = (qa.quick_wins ?? []).filter(
    (issue) => !skippedKeys.has(issueKey(issue)) && !addressedKeys.has(issueKey(issue)),
  );

  const seen = new Set<string>();
  const issues: BlockingIssue[] = [];
  for (const issue of [...blockingOpen, ...quickWinsOpen]) {
    const key = issueKey(issue);
    if (seen.has(key)) continue;
    seen.add(key);
    issues.push(issue);
  }

  return {
    issues,
    blockingCount: blockingOpen.length,
    quickWinCount: quickWinsOpen.length,
  };
}

/** Length issues cannot batch with content-adding fixes — mirror ATS Guidance batch rules. */
export function filterIssuesForChatBatch(issues: BlockingIssue[]): BlockingIssue[] {
  if (issues.length <= 1) return issues;
  const hasLength = issues.some((issue) => issue.category === "length");
  const hasNonLength = issues.some((issue) => issue.category !== "length");
  if (hasLength && hasNonLength) {
    return issues.filter((issue) => issue.category !== "length");
  }
  return issues;
}

export function partitionMechanicalAndChatIssues(
  tailored: TailoredResumeOutput,
  issues: BlockingIssue[],
): { mechanical: BlockingIssue[]; chat: BlockingIssue[] } {
  const mechanical: BlockingIssue[] = [];
  const chat: BlockingIssue[] = [];
  for (const issue of issues) {
    if (canApplyMechanicalQuickWin(tailored, issue)) {
      mechanical.push(issue);
    } else {
      chat.push(issue);
    }
  }
  const filteredChat = filterIssuesForChatBatch(chat);
  return {
    mechanical,
    chat: filteredChat.slice(0, MAX_CHAT_TARGET_ISSUES),
  };
}

export type MechanicalApplyResult = {
  resume: TailoredResumeOutput;
  appliedIssues: BlockingIssue[];
};

export function applyMechanicalQuickWins(
  tailored: TailoredResumeOutput,
  issues: BlockingIssue[],
): MechanicalApplyResult {
  let resume = tailored;
  const appliedIssues: BlockingIssue[] = [];
  for (const issue of issues) {
    const result = tryApplyMechanicalQuickWin(resume, issue);
    if (result && result.changes.length > 0) {
      resume = result.resume;
      appliedIssues.push(issue);
    }
  }
  return { resume, appliedIssues };
}

export type OrphanPatch = { patch: ResumePatch; sourceIssueKey?: string };

export type DeterministicPatchApplyResult = {
  resume: TailoredResumeOutput;
  appliedPatchCount: number;
  requestedPatchCount: number;
  orphanPatches: OrphanPatch[];
  addressedIssueKeys: string[];
};

export function applyPatchesDeterministically(
  tailored: TailoredResumeOutput,
  rawPatches: ResumePatch[],
  targetIssues: BlockingIssue[],
): DeterministicPatchApplyResult {
  const enrichedIssues = enrichIssuesWithInferredAnchors(tailored, targetIssues);
  const hydrated = hydratePatchesFromIssues(tailored, rawPatches, enrichedIssues);
  const normalized = hydrated.map((patch) => normalizeResumePatch(tailored, patch));
  const sourceIssueKeys = sourceIssueKeysForPatches(tailored, normalized, enrichedIssues);

  const entries = normalized.map((patch, index) => ({
    patch,
    sourceIssueKey: sourceIssueKeys[index],
    placeable: isPatchPlaceable(patch, tailored),
  }));

  let resume = tailored;
  let appliedPatchCount = 0;
  const orphanPatches: OrphanPatch[] = [];
  const addressedIssueKeys: string[] = [];

  for (const entry of entries) {
    if (!entry.placeable) {
      orphanPatches.push({ patch: entry.patch, sourceIssueKey: entry.sourceIssueKey });
      continue;
    }
    const patch = normalizeResumePatch(resume, entry.patch);
    const { updated, applied } = applyResumePatch(resume, patch);
    if (applied) {
      resume = updated;
      appliedPatchCount += 1;
      if (entry.sourceIssueKey) {
        addressedIssueKeys.push(entry.sourceIssueKey);
      }
    } else {
      orphanPatches.push({ patch: entry.patch, sourceIssueKey: entry.sourceIssueKey });
    }
  }

  return {
    resume,
    appliedPatchCount,
    requestedPatchCount: normalized.length,
    orphanPatches,
    addressedIssueKeys,
  };
}

export function issuesForAddressedKeys(
  resume: TailoredResumeOutput,
  catalog: BlockingIssue[],
  keys: string[],
): BlockingIssue[] {
  const enriched = enrichIssuesWithInferredAnchors(resume, catalog);
  const keySet = new Set(keys);
  const matched = new Set<string>();
  const results: BlockingIssue[] = [];

  for (const raw of catalog) {
    const enrichedIssue =
      enriched.find(
        (candidate) =>
          candidate.category === raw.category &&
          candidate.description === raw.description &&
          candidate.suggestion === raw.suggestion,
      ) ?? raw;
    const candidateKeys = [
      issueKey(raw),
      issueKey(enrichedIssue),
      issueAnchorKey(enrichedIssue),
    ];
    if (!candidateKeys.some((key) => keySet.has(key))) continue;
    const stable = issueKey(raw);
    if (matched.has(stable)) continue;
    matched.add(stable);
    results.push(raw);
  }

  return results;
}

export function buildApplyAllReport(
  appliedIssueCount: number,
  totalIssues: number,
  notAttemptedCount = 0,
): string | null {
  if (totalIssues === 0) return null;
  const unmatched = Math.max(0, totalIssues - appliedIssueCount - notAttemptedCount);
  if (appliedIssueCount === 0 && unmatched === 0 && notAttemptedCount === 0) {
    return "No improvements were applied.";
  }
  let message = `Applied ${appliedIssueCount} of ${totalIssues}`;
  if (unmatched > 0) {
    message += `; ${unmatched} could not be matched`;
  }
  if (notAttemptedCount > 0) {
    message += `; ${notAttemptedCount} not attempted this round (length conflict or batch limit)`;
  }
  message += ".";
  return message;
}

export function countNotAttemptedIssues(
  allIssues: BlockingIssue[],
  mechanicalIssues: BlockingIssue[],
  chatIssues: BlockingIssue[],
): number {
  const attempted = new Set([
    ...mechanicalIssues.map(issueKey),
    ...chatIssues.map(issueKey),
  ]);
  return allIssues.filter((issue) => !attempted.has(issueKey(issue))).length;
}

export function buildApplyAllChatMessage(
  issues: BlockingIssue[],
  tailored: TailoredResumeOutput,
): string {
  return buildBatchChatMessage(issues, tailored);
}
