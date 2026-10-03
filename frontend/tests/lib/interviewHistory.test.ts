import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  isInterviewCompleteSentinel,
  sanitizeInterviewHistory,
} from "@/lib/interviewHistory";

describe("interviewHistory", () => {
  it("drops INTERVIEW_COMPLETE interviewer rows", () => {
    const out = sanitizeInterviewHistory([
      { role: "interviewer", text: "What is your title?" },
      { role: "user", text: "Engineer at Acme" },
      { role: "interviewer", text: "INTERVIEW_COMPLETE" },
      { role: "user", text: "extra note" },
    ]);
    assert.equal(out.length, 3);
    assert.equal(out[2].role, "user");
  });

  it("detects complete sentinel", () => {
    assert.equal(isInterviewCompleteSentinel("INTERVIEW_COMPLETE"), true);
    assert.equal(isInterviewCompleteSentinel("Still working?"), false);
  });
});
