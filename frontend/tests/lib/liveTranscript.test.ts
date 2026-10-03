import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { liveVoiceTranscript } from "@/lib/voice/liveTranscript";

describe("liveVoiceTranscript", () => {
  it("returns typed base when mic is silent", () => {
    assert.equal(liveVoiceTranscript("hello", "", ""), "hello");
  });

  it("merges final and interim speech with typed prefix", () => {
    assert.equal(
      liveVoiceTranscript("I worked at", "Acme", " Corp"),
      "I worked at Acme Corp",
    );
  });
});
