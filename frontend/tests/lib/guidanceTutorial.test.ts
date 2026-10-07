import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";

const guidanceStore = new Map<string, string>();
const memoryStorage: Storage = {
  getItem: (key) => guidanceStore.get(key) ?? null,
  setItem: (key, value) => {
    guidanceStore.set(key, value);
  },
  removeItem: (key) => {
    guidanceStore.delete(key);
  },
  clear: () => guidanceStore.clear(),
  key: (index) => Array.from(guidanceStore.keys())[index] ?? null,
  get length() {
    return guidanceStore.size;
  },
};
(globalThis as { localStorage?: Storage }).localStorage = memoryStorage;
import {
  isTutorialEnabled,
  markGuidanceSeen,
  restartTutorial,
  setTutorialEnabled,
  isGuidanceSeen,
} from "@/lib/guidance/tutorial";
import { nextMasterResumeGuidanceStep } from "@/lib/guidance/masterResumeGuidance";
import { nextJobsGuidanceStep } from "@/lib/guidance/jobsGuidance";
import { nextSessionGuidanceStep } from "@/lib/guidance/sessionGuidance";

describe("tutorial storage", () => {
  beforeEach(() => {
    guidanceStore.clear();
    setTutorialEnabled(true);
    restartTutorial();
  });

  it("isTutorialEnabled defaults true", () => {
    assert.equal(isTutorialEnabled(), true);
  });

  it("setTutorialEnabled false disables guidance", () => {
    setTutorialEnabled(false);
    assert.equal(isTutorialEnabled(), false);
    assert.equal(nextJobsGuidanceStep({ beforeFirstSearch: true }), null);
  });

  it("restartTutorial clears guidance flags", () => {
    markGuidanceSeen("jobs.js1");
    assert.equal(isGuidanceSeen("jobs.js1"), true);
    restartTutorial();
    assert.equal(isGuidanceSeen("jobs.js1"), false);
  });
});

describe("nextMasterResumeGuidanceStep", () => {
  beforeEach(() => {
    guidanceStore.clear();
    setTutorialEnabled(true);
    restartTutorial();
  });

  it("returns mr1 after ingest", () => {
    assert.equal(nextMasterResumeGuidanceStep({ liveCount: 1, ingestJustFinished: true }), "master_resume.mr1");
  });
});

describe("nextJobsGuidanceStep", () => {
  beforeEach(() => {
    guidanceStore.clear();
    setTutorialEnabled(true);
    restartTutorial();
  });

  it("returns js1 before first search", () => {
    assert.equal(nextJobsGuidanceStep({ beforeFirstSearch: true }), "jobs.js1");
  });
});

describe("nextSessionGuidanceStep", () => {
  beforeEach(() => {
    guidanceStore.clear();
    setTutorialEnabled(true);
    restartTutorial();
  });

  it("returns jt1 for new session", () => {
    assert.equal(
      nextSessionGuidanceStep({ sessionId: "abc", step: "other", isNewSession: true }),
      "session.jt1",
    );
  });
});
