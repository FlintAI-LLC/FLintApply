import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { liveBackendAccessToken } from "@/lib/auth/accessToken";

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
