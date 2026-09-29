import type { QAOutput } from "@/lib/api";
import { selectOpenImprovementIssues } from "@/lib/applyAllImprovements";
import type { ResumeSuggestion } from "@/lib/suggestions";

/** Credit-confirm and UI label for a full Phase 3 forced rewrite. */
export const RE_TAILOR_ACTION_LABEL = "Re-tailor from scratch";

/** Server version-history label saved immediately before a forced re-tailor. */
export const RE_TAILOR_VERSION_SNAPSHOT_LABEL = "Before re-tailor from scratch";

export function countPendingSuggestions(suggestions: readonly ResumeSuggestion[]): number {
  return suggestions.filter((entry) => entry.status === "pending").length;
}

export function countOpenAtsImprovements(
  qa: QAOutput | null | undefined,
  addressedKeys: ReadonlySet<string>,
  skippedKeys: ReadonlySet<string>,
): number {
  return selectOpenImprovementIssues(qa, addressedKeys, skippedKeys).issues.length;
}
