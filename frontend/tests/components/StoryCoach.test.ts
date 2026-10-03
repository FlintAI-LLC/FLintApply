/**
 * Story coach UI contract tests (source-level).
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import { join } from "node:path";

const ROOT = join(import.meta.dirname, "..", "..");
const coachSource = readFileSync(
  join(ROOT, "components/profile/StoryCoach.tsx"),
  "utf8",
);
const recorderSource = readFileSync(
  join(ROOT, "components/profile/StoryRecorder.tsx"),
  "utf8",
);

describe("StoryCoach empty response handling", () => {
  it("does not append coach message when accumulated text is empty", () => {
    const slice = coachSource.slice(
      coachSource.indexOf("const coachText = accumulated.trim()"),
      coachSource.indexOf("setMessages((prev) => [...prev, { role: \"coach\""),
    );
    assert.match(slice, /if \(!coachText\)/);
    assert.doesNotMatch(slice, /setMessages/);
  });

  it("handles coach_empty SSE error code", () => {
    assert.match(coachSource, /coach_empty/);
  });
});

describe("StoryRecorder tier gating", () => {
  it("hides segment coach for free users", () => {
    assert.match(recorderSource, /showSegmentCoach/);
    assert.match(recorderSource, /showCoachButton=\{showSegmentCoach\}/);
    assert.match(recorderSource, /StoryWholeReview/);
  });
});
