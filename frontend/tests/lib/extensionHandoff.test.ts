import { describe, it, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import {
  EXTENSION_HANDOFF_TTL_MS,
  buildSessionNewUrl,
  captureExtensionHandoffFromParams,
  clearExtensionHandoff,
  getExtensionHandoff,
  isExtensionHandoffConsumed,
  markExtensionHandoffConsumed,
  parseExtensionHandoffFromUrl,
  saveExtensionHandoff,
} from "@/lib/extensionHandoff";

describe("extensionHandoff", () => {
  const storage = new Map<string, string>();

  beforeEach(() => {
    storage.clear();
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: globalThis,
    });
    Object.defineProperty(globalThis, "sessionStorage", {
      configurable: true,
      value: {
        getItem: (k: string) => storage.get(k) ?? null,
        setItem: (k: string, v: string) => storage.set(k, v),
        removeItem: (k: string) => storage.delete(k),
      },
    });
  });

  afterEach(() => {
    Reflect.deleteProperty(globalThis, "sessionStorage");
    Reflect.deleteProperty(globalThis, "window");
  });

  it("round-trips a freshly saved handoff", () => {
    saveExtensionHandoff({ jd_id: "jd-1", source: "extension", step: "jd" });
    const got = getExtensionHandoff();
    assert.equal(got?.jd_id, "jd-1");
    assert.equal(got?.source, "extension");
  });

  it("stamps captured_at automatically when not provided", () => {
    const before = Date.now();
    saveExtensionHandoff({ jd_id: "jd-1", source: "extension", step: "jd" });
    const got = getExtensionHandoff();
    assert.ok(typeof got?.captured_at === "number");
    assert.ok(got!.captured_at! >= before);
  });

  it("expires a handoff older than EXTENSION_HANDOFF_TTL_MS and clears it (AC10)", () => {
    saveExtensionHandoff({
      jd_id: "jd-stale",
      source: "extension",
      step: "jd",
      captured_at: Date.now() - EXTENSION_HANDOFF_TTL_MS - 1,
    });
    assert.equal(getExtensionHandoff(), null);
    // Expiry also clears storage so a later save/read starts clean.
    assert.equal(storage.get("sr_extension_jd_handoff"), undefined);
  });

  it("keeps a handoff just inside the TTL window", () => {
    saveExtensionHandoff({
      jd_id: "jd-fresh",
      source: "extension",
      step: "jd",
      captured_at: Date.now() - (EXTENSION_HANDOFF_TTL_MS - 1000),
    });
    assert.equal(getExtensionHandoff()?.jd_id, "jd-fresh");
  });

  it("clearExtensionHandoff removes a consumed handoff (defect #6/#9)", () => {
    saveExtensionHandoff({ jd_id: "jd-1", source: "extension", step: "jd" });
    clearExtensionHandoff();
    assert.equal(getExtensionHandoff(), null);
  });

  it("captureExtensionHandoffFromParams stores jd_id/source/step from URL params", () => {
    const params = new URLSearchParams({
      jd_id: "jd-2",
      source: "extension",
      step: "jd",
      jd_review: "1",
    });
    const handoff = captureExtensionHandoffFromParams(params);
    assert.equal(handoff?.jd_id, "jd-2");
    assert.equal(handoff?.jd_review, true);
    assert.equal(getExtensionHandoff()?.jd_id, "jd-2");
  });

  it("captureExtensionHandoffFromParams returns null without a jd_id and does not touch storage", () => {
    const handoff = captureExtensionHandoffFromParams(new URLSearchParams());
    assert.equal(handoff, null);
    assert.equal(getExtensionHandoff(), null);
  });

  it("markExtensionHandoffConsumed / isExtensionHandoffConsumed round-trip by jd_id", () => {
    assert.equal(isExtensionHandoffConsumed("jd-5"), false);
    markExtensionHandoffConsumed("jd-5");
    assert.equal(isExtensionHandoffConsumed("jd-5"), true);
    // A different jd_id is unaffected — the marker is scoped, not global.
    assert.equal(isExtensionHandoffConsumed("jd-6"), false);
  });

  it("saveExtensionHandoff is a no-op once the jd_id is marked consumed (AC9)", () => {
    markExtensionHandoffConsumed("jd-7");
    saveExtensionHandoff({ jd_id: "jd-7", source: "extension", step: "jd" });
    assert.equal(getExtensionHandoff(), null);
  });

  it("captureExtensionHandoffFromParams re-deriving the SAME consumed jd_id from the URL does not resurrect it (AC9)", () => {
    // Mirrors goTo() re-adding jd_id to the URL after the handoff that jd_id
    // was already consumed on a step transition.
    markExtensionHandoffConsumed("jd-8");
    const params = new URLSearchParams({ jd_id: "jd-8", source: "extension", step: "info" });
    captureExtensionHandoffFromParams(params);
    assert.equal(getExtensionHandoff(), null);
  });

  it("saveExtensionHandoff is a no-op for a non-extension source (S3)", () => {
    saveExtensionHandoff({ jd_id: "jd-9", source: "jobs", step: "jd" });
    assert.equal(getExtensionHandoff(), null);
  });

  it("parseExtensionHandoffFromUrl reads jd_id/source/step out of a callbackUrl-style path", () => {
    // No `window.location` in this harness — parseExtensionHandoffFromUrl
    // falls back to a fixed base URL when `window` is undefined, which is
    // exactly the SSR-safe path this assertion exercises.
    Reflect.deleteProperty(globalThis, "window");
    const handoff = parseExtensionHandoffFromUrl(
      "/session/new?jd_id=jd-3&source=extension&step=jd",
    );
    assert.deepEqual(handoff, {
      jd_id: "jd-3",
      source: "extension",
      step: "jd",
      jd_review: false,
    });
  });

  it("buildSessionNewUrl builds the documented wizard URL shape", () => {
    const url = buildSessionNewUrl({ jd_id: "jd-4", source: "extension", step: "jd" });
    assert.equal(url, "/session/new?step=jd&jd_id=jd-4&source=extension");
  });

  it("buildSessionNewUrl adds jd_review=1 only when set", () => {
    const url = buildSessionNewUrl({
      jd_id: "jd-4",
      source: "extension",
      step: "jd",
      jd_review: true,
    });
    assert.match(url, /jd_review=1/);
  });
});
