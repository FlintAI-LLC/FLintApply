import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import type { QAOutput } from "@/lib/api";
import {
  countOpenAtsImprovements,
  countPendingSuggestions,
  RE_TAILOR_ACTION_LABEL,
  RE_TAILOR_VERSION_SNAPSHOT_LABEL,
} from "@/lib/reTailor";
import type { ResumeSuggestion } from "@/lib/suggestions";

function suggestion(status: ResumeSuggestion["status"]): ResumeSuggestion {
  return {
    id: status,
    patch: { section: "summary", new_summary: "x" },
    status,
  };
}

describe("reTailor helpers", () => {
  it("counts only pending suggestions", () => {
    const suggestions = [
      suggestion("pending"),
      suggestion("accepted"),
      suggestion("rejected"),
    ];
    assert.equal(countPendingSuggestions(suggestions), 1);
  });

  it("counts open ATS issues with skip and addressed semantics", () => {
    const qa = {
      ats_score: 40,
      blocking_issues: [
        {
          category: "bullet",
          impact: "medium",
          fix_effort: "user_input",
          description: "Open",
          suggestion: "Fix",
        },
        {
          category: "bullet",
          impact: "medium",
          fix_effort: "user_input",
          description: "Done",
          suggestion: "Done fix",
        },
      ],
      quick_wins: [
        {
          category: "keyword",
          impact: "low",
          fix_effort: "one_click",
          description: "Quick",
          suggestion: 'Add "Go" to the Skills section',
        },
      ],
    } as QAOutput;
    const addressed = new Set<string>(["bullet|Done|Done fix"]);
    const skipped = new Set<string>(["keyword|Quick|Add \"Go\" to the Skills section"]);
    assert.equal(countOpenAtsImprovements(qa, addressed, skipped), 1);
    assert.equal(countOpenAtsImprovements(null, addressed, skipped), 0);
  });

  it("exposes stable action and snapshot labels", () => {
    assert.equal(RE_TAILOR_ACTION_LABEL, "Re-tailor from scratch");
    assert.equal(RE_TAILOR_VERSION_SNAPSHOT_LABEL, "Before re-tailor from scratch");
  });
});

describe("reTailor wiring", () => {
  const pageSource = readFileSync(
    path.join(process.cwd(), "app/session/[id]/page.tsx"),
    "utf8",
  );

  it("opens confirm instead of forcing phase 3 from the header button", () => {
    const openIdx = pageSource.indexOf("onClick={() => setReTailorConfirmOpen(true)}");
    assert.ok(openIdx >= 0);
    const headerSlice = pageSource.slice(openIdx, openIdx + 400);
    assert.doesNotMatch(headerSlice, /runCurrentPhase\(\{ force: true \}\)/);
    assert.match(pageSource, /onConfirm=\{\(\) => void executeReTailorFromScratch\(\)\}/);
  });

  it("aborts re-tailor when the version snapshot fails", () => {
    const executeSlice = pageSource.slice(
      pageSource.indexOf("const executeReTailorFromScratch"),
      pageSource.indexOf("useEffect(() => {", pageSource.indexOf("const executeReTailorFromScratch")),
    );
    assert.match(executeSlice, /saveTailoredVersionSnapshot\([\s\S]*RE_TAILOR_VERSION_SNAPSHOT_LABEL/);
    const catchIdx = executeSlice.indexOf("Could not save a version snapshot");
    const returnIdx = executeSlice.indexOf("return;", catchIdx);
    const forceIdx = executeSlice.indexOf("runCurrentPhase({ force: true })");
    assert.ok(catchIdx >= 0 && returnIdx > catchIdx && forceIdx > returnIdx);
  });

  it("skips phase 3 partial apply only inside the guarded branch", () => {
    const partialSlice = pageSource.slice(
      pageSource.indexOf('lastEvent.event === "partial"'),
      pageSource.indexOf('lastEvent.event === "cost_estimate"'),
    );
    assert.match(partialSlice, /if \(!skipPhase3Partial\) \{[\s\S]*applyPhaseOutputByNumber/);
  });
});
