import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  liveBackendAccessToken,
  needsBackendAccessRefresh,
  expiredSessionAuthUrl,
  resolveBackendAuthState,
} from "@/lib/auth/accessToken";

describe("liveBackendAccessToken", () => {
  it("returns the token when it is still live", () => {
    assert.equal(
      liveBackendAccessToken({
        backendAccessToken: "tok",
        backendExpiresAt: Date.now() + 60_000,
      }),
      "tok",
    );
  });

  it("hides a NextAuth TokenExpired session", () => {
    assert.equal(
      liveBackendAccessToken({
        backendAccessToken: "tok",
        error: "TokenExpired",
        backendExpiresAt: Date.now() + 60_000,
      }),
      undefined,
    );
  });

  it("hides a JWT that is past backendExpiresAt", () => {
    assert.equal(
      liveBackendAccessToken({
        backendAccessToken: "tok",
        backendExpiresAt: Date.now() - 1,
      }),
      undefined,
    );
  });

  it("returns undefined without a token", () => {
    assert.equal(liveBackendAccessToken(null), undefined);
    assert.equal(liveBackendAccessToken({}), undefined);
  });
});

describe("needsBackendAccessRefresh", () => {
  it("is false without a held token", () => {
    assert.equal(needsBackendAccessRefresh(null), false);
    assert.equal(needsBackendAccessRefresh({}), false);
  });

  it("flags TokenExpired even when expiry metadata is still in the future", () => {
    assert.equal(
      needsBackendAccessRefresh({
        backendAccessToken: "tok",
        error: "TokenExpired",
        backendExpiresAt: Date.now() + 60_000,
      }),
      true,
    );
  });

  it("flags a held-but-dead JWT for refresh", () => {
    assert.equal(
      needsBackendAccessRefresh({
        backendAccessToken: "tok",
        backendExpiresAt: Date.now() - 1,
      }),
      true,
    );
    assert.equal(
      needsBackendAccessRefresh({
        backendAccessToken: "tok",
        backendExpiresAt: Date.now() + 60_000,
      }),
      false,
    );
  });
});

describe("resolveBackendAuthState", () => {
  it("waits while authenticated but the JWT is past expiry", () => {
    const state = resolveBackendAuthState(
      {
        backendAccessToken: "tok",
        backendExpiresAt: Date.now() - 1,
      },
      "authenticated",
    );
    assert.equal(state.token, undefined);
    assert.equal(state.pendingRefresh, true);
    assert.equal(state.authLoading, true);
  });

  it("does not auth-load forever when unauthenticated", () => {
    const state = resolveBackendAuthState(
      { backendAccessToken: "tok", backendExpiresAt: Date.now() + 60_000 },
      "unauthenticated",
    );
    assert.equal(state.token, undefined);
    assert.equal(state.authLoading, false);
  });

  it("exposes a live token when authenticated and not expired", () => {
    const state = resolveBackendAuthState(
      {
        backendAccessToken: "tok",
        backendExpiresAt: Date.now() + 60_000,
      },
      "authenticated",
    );
    assert.equal(state.token, "tok");
    assert.equal(state.authLoading, false);
  });
});

describe("expiredSessionAuthUrl", () => {
  it("builds a sign-in URL without leaking the API error", () => {
    const url = expiredSessionAuthUrl("/onboarding?step=2");
    assert.match(url, /^\/auth\?callbackUrl=/);
    assert.doesNotMatch(url, /Access token expired/);
    assert.match(url, /onboarding/);
  });
});
