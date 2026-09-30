import { describe, it } from "node:test";
import assert from "node:assert/strict";
import type { ResumePatch } from "@/lib/api";
import { mergeSuggestionBatch, patchFingerprint } from "@/lib/suggestions";

function summaryPatch(text: string): ResumePatch {
  return {
    section: "summary",
    new_summary: text,
    bullet_old: "8+ years",
    bullet_new: "Eight plus years",
  };
}

describe("dismissed suggestion fingerprints", () => {
  it("blocks re-adding the same patch in mergeSuggestionBatch", () => {
    const patch = summaryPatch("Eight plus years of experience.");
    const dismissed = new Set([patchFingerprint(patch)]);
    const merged = mergeSuggestionBatch([], [patch], [undefined], dismissed);
    assert.equal(merged.length, 0);
  });

  it("keeps non-dismissed siblings with their own source keys", () => {
    const dismissedPatch = summaryPatch("Dismissed summary.");
    const keptPatch = summaryPatch("Kept summary.");
    const merged = mergeSuggestionBatch(
      [],
      [dismissedPatch, keptPatch],
      ["key-dismissed", "key-kept"],
      new Set([patchFingerprint(dismissedPatch)]),
    );
    assert.equal(merged.length, 1);
    assert.equal(merged[0]!.sourceIssueKey, "key-kept");
    assert.equal(merged[0]!.patch.new_summary, "Kept summary.");
  });

  it("gives distinct patches distinct fingerprints", () => {
    assert.notEqual(
      patchFingerprint(summaryPatch("A")),
      patchFingerprint(summaryPatch("B")),
    );
  });
});
