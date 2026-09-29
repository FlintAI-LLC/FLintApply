import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { classifyJdLoadError, EMPTY_JD_TEXT_ERROR } from "@/lib/jdLoadError";
import { ExtensionJobDescriptionError } from "@/lib/extensionJobDescription";
import { ApiError } from "@/lib/api";

describe("classifyJdLoadError", () => {
  it("classifies a 401 from the extension JD endpoint as unauthorized", () => {
    const result = classifyJdLoadError(new ExtensionJobDescriptionError(401));
    assert.equal(result.kind, "unauthorized");
    assert.match(result.message, /sign in again/i);
  });

  it("classifies a 404 from the extension JD endpoint as not_found without leaking IDOR detail", () => {
    const result = classifyJdLoadError(new ExtensionJobDescriptionError(404));
    assert.equal(result.kind, "not_found");
    // Must not claim certainty about *why* — the backend intentionally
    // collapses "deleted" and "different account" into one 404 (I1).
    assert.match(result.message, /different account|expired/i);
  });

  it("classifies a 401 from the jobs API (ApiError) the same as the extension path", () => {
    const result = classifyJdLoadError(new ApiError("Unauthorized", 401));
    assert.equal(result.kind, "unauthorized");
  });

  it("classifies a 404 from the jobs API (ApiError) the same as the extension path", () => {
    const result = classifyJdLoadError(new ApiError("Not found", 404));
    assert.equal(result.kind, "not_found");
  });

  it("classifies an unexpected HTTP status as a server error, still with a message", () => {
    const result = classifyJdLoadError(new ExtensionJobDescriptionError(500));
    assert.equal(result.kind, "server_error");
    assert.ok(result.message.length > 0);
  });

  it("classifies a bare fetch failure (no HTTP status) as network", () => {
    const result = classifyJdLoadError(new TypeError("Failed to fetch"));
    assert.equal(result.kind, "network");
    assert.ok(result.message.length > 0);
  });

  it("classifies a non-Error throw as network without crashing", () => {
    const result = classifyJdLoadError("some string throw");
    assert.equal(result.kind, "network");
  });
});

describe("EMPTY_JD_TEXT_ERROR", () => {
  it("is a distinct, non-empty message for captured-but-empty JD text", () => {
    assert.equal(EMPTY_JD_TEXT_ERROR.kind, "empty");
    assert.ok(EMPTY_JD_TEXT_ERROR.message.length > 0);
  });
});
