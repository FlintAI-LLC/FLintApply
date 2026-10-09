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
import { nextCareerWatchGuidanceStep } from "@/lib/guidance/careerWatchGuidance";
import { nextNotificationsGuidanceStep } from "@/lib/guidance/notificationsGuidance";
import { GUIDANCE_CONTENT } from "@/lib/guidance/content";
import { GUIDE_TOPIC_GROUPS } from "@/lib/guidance/guideTopics";

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

describe("nextCareerWatchGuidanceStep", () => {
  beforeEach(() => {
    guidanceStore.clear();
    setTutorialEnabled(true);
    restartTutorial();
  });

  it("returns cw1 on empty watchlist", () => {
    assert.equal(
      nextCareerWatchGuidanceStep({ watchCount: 0, alertCount: 0 }),
      "career_watch.cw1",
    );
  });

  it("returns cw2 after cw1 when keywords field focused", () => {
    markGuidanceSeen("career_watch.cw1");
    assert.equal(
      nextCareerWatchGuidanceStep({
        watchCount: 0,
        keywordsFieldFocused: true,
        alertCount: 0,
      }),
      "career_watch.cw2",
    );
  });
});

describe("nextNotificationsGuidanceStep", () => {
  beforeEach(() => {
    guidanceStore.clear();
    setTutorialEnabled(true);
    restartTutorial();
  });

  it("chains no1 through no5", () => {
    assert.equal(nextNotificationsGuidanceStep(), "notifications.no1");
    markGuidanceSeen("notifications.no1");
    assert.equal(nextNotificationsGuidanceStep(), "notifications.no2");
  });
});

describe("guide topic coverage", () => {
  it("every grouped step has content", () => {
    for (const group of GUIDE_TOPIC_GROUPS) {
      for (const id of group.steps) {
        assert.ok(GUIDANCE_CONTENT[id], `missing content for ${id}`);
      }
    }
  });
});
