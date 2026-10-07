import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  deriveAtsScoreRefreshMode,
  sessionHasPhase4Score,
} from "@/components/session/AtsScoreRefreshControls";

describe("deriveAtsScoreRefreshMode", () => {
  it("routes stale sessions without a prior score to initial scoring", () => {
    assert.equal(
      deriveAtsScoreRefreshMode({
        staleSince: "2026-10-06T00:00:00.000Z",
        pendingPaidConfirm: false,
        hasPriorScore: false,
      }),
      "needs_initial_score",
    );
  });

  it("allows free rescore when stale and a prior score exists", () => {
    assert.equal(
      deriveAtsScoreRefreshMode({
        staleSince: "2026-10-06T00:00:00.000Z",
        pendingPaidConfirm: false,
        hasPriorScore: true,
      }),
      "stale_free",
    );
  });
});

describe("sessionHasPhase4Score", () => {
  it("detects stored phase 4 output", () => {
    assert.equal(
      sessionHasPhase4Score({
        "4": { output: { ats_score: 72 } },
      }),
      true,
    );
    assert.equal(sessionHasPhase4Score({ "4": { output: {} } }), false);
  });
});
