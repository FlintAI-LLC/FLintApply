import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  blockingSkillLintIssues,
  isValidSkillKeyword,
  stripBlockingSkillTerms,
  formatTailoredLintErrors,
} from "@/lib/tailoredLint";
import type { TailoredResumeOutput } from "@/lib/api";

describe("tailoredLint", () => {
  it("rejects JD prose masquerading as skills (ST-017)", () => {
    assert.equal(
      isValidSkillKeyword("scripting (Python or Bash) for automation and tooling"),
      false,
    );
    assert.equal(
      isValidSkillKeyword("Collaborate with stakeholders in Finance"),
      false,
    );
    assert.equal(isValidSkillKeyword("Kubernetes"), true);
    assert.equal(isValidSkillKeyword("attention to detail"), true);
  });

  it("stripBlockingSkillTerms removes invalid skill terms before save", () => {
    const tailored: TailoredResumeOutput = {
      summary: "Summary",
      experience: [],
      skills: [
        "Technical: Python, scripting (Python or Bash) for automation and tooling, Docker",
        "Soft: Collaborate with stakeholders in Finance, communication",
      ],
    };
    const cleaned = stripBlockingSkillTerms(tailored);
    const flat = cleaned.skills.join(" ");
    assert.match(flat, /Python/);
    assert.match(flat, /Docker/);
    assert.doesNotMatch(flat, /automation and tooling/);
    assert.doesNotMatch(flat, /Collaborate with stakeholders/);
    assert.equal(blockingSkillLintIssues(cleaned.skills ?? []).length, 0);
  });

  it("formatTailoredLintErrors lists field errors for the UI", () => {
    const message = formatTailoredLintErrors([
      {
        field: "skills[24]",
        rule: "skill_is_sentence",
        original: "scripting (Python or Bash) for automation and tooling",
      },
    ]);
    assert.match(message, /skill_is_sentence/);
    assert.match(message, /scripting/);
  });
});
