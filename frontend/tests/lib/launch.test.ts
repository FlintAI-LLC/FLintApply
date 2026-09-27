import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  DEFAULT_LAUNCH_AT_ISO,
  formatLaunchCountdown,
  formatLaunchDatePacific,
  isLaunchOpen,
  launchAtFromEnv,
  msUntilLaunch,
} from "@/lib/launch";

describe("launch", () => {
  it("parses default Pacific launch instant", () => {
    const at = launchAtFromEnv(DEFAULT_LAUNCH_AT_ISO);
    assert.ok(at);
    assert.equal(at!.toISOString(), "2026-10-15T16:00:00.000Z");
  });

  it("formats default launch as Thursday morning Pacific", () => {
    const at = launchAtFromEnv(DEFAULT_LAUNCH_AT_ISO);
    assert.ok(at);
    const label = formatLaunchDatePacific(at!);
    assert.match(label, /Thursday/);
    assert.match(label, /October 15/);
    assert.match(label, /9:00\sAM/);
    assert.match(label, /PDT|GMT-7/);
  });

  it("treats time before launch as closed", () => {
    const at = launchAtFromEnv(DEFAULT_LAUNCH_AT_ISO);
    const before = new Date("2026-09-30T23:59:00.000Z");
    assert.equal(isLaunchOpen(before, at), false);
    assert.ok(msUntilLaunch(before, at!) > 0);
  });

  it("formats countdown with days", () => {
    assert.match(formatLaunchCountdown(2 * 86400 * 1000 + 3600 * 1000), /^2d /);
  });
});
