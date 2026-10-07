import { describe, it } from "node:test";
import assert from "node:assert/strict";
import type { BlockingIssue, TailoredResumeOutput } from "@/lib/api";
import { locateIssueHint, resolveIssueAnchor, searchTermsForIssue } from "@/lib/issueLocate";

const resume: TailoredResumeOutput = {
  contact: { name: "Jane" },
  summary: "Engineer with proven delivery in Kubernetes platforms.",
  skills: ["Platform: Python"],
  experience: [
    {
      title: "Staff Engineer",
      company: "Acme",
      dates: "2020-2024",
      bullets: ["Led proven rollout of inference stack"],
    },
  ],
  education: [],
  projects: [],
  certifications: [],
};

describe("searchTermsForIssue", () => {
  it("ignores stopwords like Many from bulk keyword prose", () => {
    const issue: BlockingIssue = {
      category: "keyword",
      description: "Many must-have keywords absent from the resume.",
      suggestion: "Add missing terms where you have evidence.",
      impact: "high",
      fix_effort: "one_click",
    };
    const terms = searchTermsForIssue(issue);
    assert.ok(!terms.some((t) => t === "Many"));
  });
});

describe("resolveIssueAnchor", () => {
  it("finds summary when JD tone mentions vocabulary not in bullets", () => {
    const issue: BlockingIssue = {
      category: "bullet",
      description: "JD tone alignment",
      suggestion: "Mirror JD vocabulary proven in the summary.",
      impact: "medium",
      fix_effort: "manual_rewrite",
    };
    const terms = searchTermsForIssue(issue);
    assert.ok(terms.some((t) => t.toLowerCase().includes("proven")));
    const anchor = resolveIssueAnchor(issue, resume);
    assert.equal(anchor?.section, "summary");
    const hint = locateIssueHint(issue, resume);
    assert.equal(hint, null);
  });

  it("uses model anchor when present", () => {
    const issue: BlockingIssue = {
      category: "bullet",
      description: "Weak bullet",
      suggestion: "Fix it",
      impact: "low",
      fix_effort: "manual_rewrite",
      anchor: { section: "experience", entry_index: 0, bullet_index: 0 },
    };
    assert.deepEqual(resolveIssueAnchor(issue, resume), issue.anchor);
  });
});
