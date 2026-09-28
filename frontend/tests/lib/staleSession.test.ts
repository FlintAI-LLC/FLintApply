import { describe, it } from "node:test"
import assert from "node:assert/strict"
import { isStaleAuthError } from "@/lib/auth/staleSession"

describe("isStaleAuthError", () => {
  it("treats an expired access token as a session to clear", () => {
    assert.equal(isStaleAuthError("Access token expired"), true)
    assert.equal(isStaleAuthError("Invalid access token"), true)
  })

  it("does not treat unrelated API errors as sign-out", () => {
    assert.equal(isStaleAuthError("Could not load onboarding progress."), false)
    assert.equal(isStaleAuthError("Not signed in"), false)
  })
})
