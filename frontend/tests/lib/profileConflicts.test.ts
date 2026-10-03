import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { dedupeResumeRoleConflicts } from "@/lib/profile";

describe("dedupeResumeRoleConflicts", () => {
  it("collapses repeated company/title pairs", () => {
    const rows = dedupeResumeRoleConflicts([
      { company: "IdMe24", existing: "Software Engineer", new: "Architect" },
      { company: "IdMe24", existing: "Software Engineer", new: "Architect" },
    ]);
    assert.equal(rows.length, 1);
  });
});
