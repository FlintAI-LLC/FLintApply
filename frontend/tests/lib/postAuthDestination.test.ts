import { describe, it, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { resolvePostAuthClientDestination } from "@/lib/auth/onboarding";
import { saveExtensionHandoff } from "@/lib/extensionHandoff";
import {
  readAuthReturnCookie,
  resolveAuthReturnUrl,
  saveAuthReturnUrl,
} from "@/lib/auth/returnUrl";

describe("resolvePostAuthClientDestination", () => {
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

  it("prefers callbackUrl over extension handoff", () => {
    saveExtensionHandoff({
      jd_id: "jd-ext",
      source: "extension",
      step: "jd",
    });
    assert.equal(
      resolvePostAuthClientDestination("/jobs"),
      "/jobs",
    );
  });

  it("uses extension handoff when callback resolves to dashboard", () => {
    saveExtensionHandoff({
      jd_id: "jd-ext",
      source: "extension",
      step: "jd",
    });
    const dest = resolvePostAuthClientDestination(null);
    assert.match(dest, /^\/session\/new\?/);
    assert.match(dest, /jd_id=jd-ext/);
  });

  it("rejects an off-origin callbackUrl and falls back to /dashboard", () => {
    assert.equal(
      resolvePostAuthClientDestination("https://evil.example/attack"),
      "/dashboard",
    );
  });

  it("rejects an off-origin stored return path (the sessionStorage leg feeding window.location.assign) and falls back to /dashboard", () => {
    saveAuthReturnUrl("https://evil.example/attack");
    assert.equal(resolveAuthReturnUrl(null), "/dashboard");
  });
});

describe("readAuthReturnCookie", () => {
  it("rejects open redirects", () => {
    assert.equal(readAuthReturnCookie("//evil"), null);
    assert.equal(readAuthReturnCookie("https://evil"), null);
  });

  it("accepts same-origin paths with query", () => {
    assert.equal(
      readAuthReturnCookie("/session/new?jd_id=abc&source=extension"),
      "/session/new?jd_id=abc&source=extension",
    );
  });
});
