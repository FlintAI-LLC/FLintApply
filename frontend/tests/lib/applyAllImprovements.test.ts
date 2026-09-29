import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import type { BlockingIssue, QAOutput, TailoredResumeOutput } from "@/lib/api";
import {
  applyMechanicalQuickWins,
  applyPatchesDeterministically,
  buildApplyAllReport,
  countNotAttemptedIssues,
  filterIssuesForChatBatch,
  issuesForAddressedKeys,
  MAX_CHAT_TARGET_ISSUES,
  partitionMechanicalAndChatIssues,
  selectOpenImprovementIssues,
} from "@/lib/applyAllImprovements";

function issue(partial: Partial<BlockingIssue> & Pick<BlockingIssue, "description" | "suggestion">): BlockingIssue {
  return {
    category: "keyword",
    impact: "medium",
    fix_effort: "user_input",
    ...partial,
  };
}

function qa(partial: Partial<QAOutput>): QAOutput {
  return {
    ats_score: 50,
    blocking_issues: [],
    quick_wins: [],
    ...partial,
  } as QAOutput;
}

function tailored(overrides: Partial<TailoredResumeOutput> = {}): TailoredResumeOutput {
  return {
    contact: {},
    summary: "Backend engineer.",
    skills: ["Languages: Python"],
    experience: [
      { title: "Engineer", company: "Acme", dates: "2020", bullets: ["Built APIs."] },
    ],
    projects: [],
    education: [],
    certifications: [],
    rewrite_notes: [],
    metrics_needed: [],
    ...overrides,
  } as TailoredResumeOutput;
}

describe("selectOpenImprovementIssues", () => {
  it("excludes skipped and addressed keys", () => {
    const open = issue({
      description: "Missing keyword",
      suggestion: 'Add "Rust" to the Skills section',
      fix_effort: "one_click",
      category: "keyword",
    });
    const skipped = issue({ description: "Skip me", suggestion: "x" });
    const addressed = issue({ description: "Done", suggestion: "y" });
    const output = qa({
      blocking_issues: [open, skipped, addressed],
      quick_wins: [],
    });
    const selection = selectOpenImprovementIssues(
      output,
      new Set(["keyword|Done|y"]),
      new Set(["keyword|Skip me|x"]),
    );
    assert.equal(selection.issues.length, 1);
    assert.equal(selection.issues[0]!.description, "Missing keyword");
  });

  it("merges quick wins without duplicating the same key", () => {
    const shared = issue({
      anchor: { section: "experience", entry_index: 0, bullet_index: 0 },
      description: "Weak bullet",
      suggestion: "Add metrics",
      category: "bullet",
    });
    const output = qa({
      blocking_issues: [shared],
      quick_wins: [{ ...shared, impact: "low" }],
    });
    const selection = selectOpenImprovementIssues(output, new Set(), new Set());
    assert.equal(selection.issues.length, 1);
    assert.equal(selection.quickWinCount, 1);
    assert.equal(selection.blockingCount, 1);
  });
});

describe("filterIssuesForChatBatch", () => {
  it("drops length issues when mixed with other categories", () => {
    const length = issue({ category: "length", description: "Too long", suggestion: "Trim" });
    const bullet = issue({ category: "bullet", description: "Weak", suggestion: "Improve" });
    const filtered = filterIssuesForChatBatch([length, bullet]);
    assert.deepEqual(filtered, [bullet]);
  });

  it("keeps length-only batches", () => {
    const length = issue({ category: "length", description: "Too long", suggestion: "Trim" });
    assert.deepEqual(filterIssuesForChatBatch([length]), [length]);
  });
});

describe("partitionMechanicalAndChatIssues", () => {
  it("routes one-click keyword fixes to mechanical", () => {
    const mechanicalIssue = issue({
      description: "Missing Rust",
      suggestion: 'Add "Rust" to the Skills section',
      fix_effort: "one_click",
      category: "keyword",
    });
    const chatIssue = issue({
      description: "Weak bullet",
      suggestion: "Quantify impact",
      category: "bullet",
    });
    const resume = tailored();
    const parts = partitionMechanicalAndChatIssues(resume, [mechanicalIssue, chatIssue]);
    assert.equal(parts.mechanical.length, 1);
    assert.equal(parts.chat.length, 1);
    assert.equal(parts.chat[0]!.category, "bullet");
  });
});

describe("applyMechanicalQuickWins", () => {
  it("applies skills keyword adds", () => {
    const rust = issue({
      description: "Missing Rust",
      suggestion: 'Add "Rust" to the Skills section',
      fix_effort: "one_click",
      category: "keyword",
    });
    const result = applyMechanicalQuickWins(tailored(), [rust]);
    assert.equal(result.appliedIssues.length, 1);
    assert.ok(result.resume.skills?.some((line) => line.includes("Rust")));
  });

  it("skips issues that cannot be applied mechanically", () => {
    const already = issue({
      description: "Has Python",
      suggestion: 'Add "Python" to the Skills section',
      fix_effort: "one_click",
      category: "keyword",
    });
    const base = tailored();
    const result = applyMechanicalQuickWins(base, [already]);
    assert.equal(result.appliedIssues.length, 0);
    assert.deepEqual(result.resume, base);
  });
});

describe("partitionMechanicalAndChatIssues", () => {
  it("drops length issues from chat when mixed with content fixes", () => {
    const keyword = issue({
      description: "Missing Go",
      suggestion: 'Add "Go" to the Skills section',
      fix_effort: "one_click",
      category: "keyword",
    });
    const length = issue({ category: "length", description: "Too long", suggestion: "Trim" });
    const bullet = issue({ category: "bullet", description: "Weak", suggestion: "Add metrics" });
    const resume = tailored();
    const parts = partitionMechanicalAndChatIssues(resume, [keyword, length, bullet]);
    assert.equal(parts.mechanical.length, 1);
    assert.deepEqual(parts.chat, [bullet]);
  });

  it("caps chat issues at the backend limit", () => {
    const chatIssues = Array.from({ length: MAX_CHAT_TARGET_ISSUES + 3 }, (_, index) =>
      issue({
        category: "bullet",
        description: `Issue ${index}`,
        suggestion: `Fix ${index}`,
      }),
    );
    const parts = partitionMechanicalAndChatIssues(tailored(), chatIssues);
    assert.equal(parts.chat.length, MAX_CHAT_TARGET_ISSUES);
  });
});

describe("applyPatchesDeterministically", () => {
  it("applies a placeable bullet patch and records the issue key", () => {
    const resume = tailored();
    const target = issue({
      category: "bullet",
      description: "Weak bullet",
      suggestion: "Quantify",
      anchor: { section: "experience", entry_index: 0, bullet_index: 0 },
    });
    const patches = [
      {
        section: "experience" as const,
        company: "Acme",
        bullet_old: "Built APIs.",
        bullet_new: "Built APIs serving 1M requests/day.",
      },
    ];
    const result = applyPatchesDeterministically(resume, patches, [target]);
    assert.equal(result.appliedPatchCount, 1);
    assert.equal(result.orphanPatches.length, 0);
    assert.ok(result.addressedIssueKeys.length > 0);
    assert.match(result.resume.experience[0]!.bullets[0]!, /1M/);
  });

  it("returns orphans when the patch cannot be placed", () => {
    const resume = tailored();
    const target = issue({
      category: "keyword",
      description: "Remove fake skill",
      suggestion: "Drop unused skill",
    });
    const patches = [{ section: "skills" as const, remove_skills: ["NotARealSkill"] }];
    const result = applyPatchesDeterministically(resume, patches, [target]);
    assert.equal(result.appliedPatchCount, 0);
    assert.equal(result.orphanPatches.length, 1);
    assert.equal(result.addressedIssueKeys.length, 0);
    assert.deepEqual(result.resume, resume);
  });
});

describe("issuesForAddressedKeys", () => {
  it("maps anchor keys from patches back to raw catalog rows", () => {
    const resume = tailored();
    const raw = issue({
      category: "bullet",
      description: "Weak bullet",
      suggestion: "Quantify",
      anchor: { section: "experience", entry_index: 0, bullet_index: 0 },
    });
    const matched = issuesForAddressedKeys(resume, [raw], ["anchor:experience:0:0"]);
    assert.equal(matched.length, 1);
    assert.equal(matched[0]!.description, raw.description);
  });
});

describe("buildApplyAllReport", () => {
  it("formats applied vs unmatched honestly", () => {
    assert.equal(buildApplyAllReport(3, 5), "Applied 3 of 5; 2 could not be matched.");
  });

  it("separates not-attempted issues from unmatched", () => {
    assert.equal(
      buildApplyAllReport(2, 5, 2),
      "Applied 2 of 5; 1 could not be matched; 2 not attempted this round (length conflict or batch limit).",
    );
  });

  it("returns null when there is nothing to report", () => {
    assert.equal(buildApplyAllReport(0, 0), null);
  });
});

describe("countNotAttemptedIssues", () => {
  it("counts length issues dropped from the chat batch", () => {
    const length = issue({ category: "length", description: "Too long", suggestion: "Trim" });
    const bullet = issue({ category: "bullet", description: "Weak", suggestion: "Fix" });
    const mechanical = issue({
      category: "keyword",
      description: "Rust",
      suggestion: 'Add "Rust" to the Skills section',
      fix_effort: "one_click",
    });
    const chat = [bullet];
    const count = countNotAttemptedIssues([mechanical, length, bullet], [mechanical], chat);
    assert.equal(count, 1);
  });
});

describe("applyAllImprovements wiring", () => {
  const pageSource = readFileSync(
    path.join(process.cwd(), "app/session/[id]/page.tsx"),
    "utf8",
  );
  const panelSource = readFileSync(
    path.join(process.cwd(), "components/session/ATSGuidancePanel.tsx"),
    "utf8",
  );

  it("session page imports apply-all helpers and chat API", () => {
    assert.match(pageSource, /from "@\/lib\/applyAllImprovements"/);
    assert.match(pageSource, /chatWithResume/);
    assert.match(pageSource, /applyAllImprovements/);
  });

  it("releases apply-all in-flight guard before ATS recalculation", () => {
    const slice = pageSource.slice(
      pageSource.indexOf("const applyAllImprovements"),
      pageSource.indexOf("const runCurrentPhase"),
    );
    const releaseIdx = slice.indexOf("applyAllInFlightRef.current = false");
    const recalcIdx = slice.indexOf("recalculateAts({ resume: current })");
    assert.ok(releaseIdx >= 0 && recalcIdx > releaseIdx);
  });

  it("ATS panel exposes Apply all improvements handler", () => {
    assert.match(panelSource, /onApplyAllImprovements/);
    assert.match(panelSource, /Apply all improvements/);
  });
});
