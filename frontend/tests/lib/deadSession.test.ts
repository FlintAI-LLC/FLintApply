import { describe, it } from "node:test"
import assert from "node:assert/strict"
import {
  UNRECOVERABLE_GRACE_MS,
  shouldSignOutForDeadSession,
} from "@/lib/auth/deadSession"

const base = { unusable: true, dead: false, exhausted: false, unusableForMs: 0 }

describe("shouldSignOutForDeadSession", () => {
  it("never signs out while the token is still usable", () => {
    assert.equal(
      shouldSignOutForDeadSession({
        ...base,
        unusable: false,
        dead: true,
        exhausted: true,
        unusableForMs: UNRECOVERABLE_GRACE_MS * 10,
      }),
      false,
    )
  })

  it("signs out immediately when the refresh cookie was rejected", () => {
    assert.equal(shouldSignOutForDeadSession({ ...base, dead: true }), true)
  })

  it("waits out the grace period when only retries are exhausted", () => {
    const exhausted = { ...base, exhausted: true }
    assert.equal(
      shouldSignOutForDeadSession({ ...exhausted, unusableForMs: UNRECOVERABLE_GRACE_MS - 1 }),
      false,
    )
    assert.equal(
      shouldSignOutForDeadSession({ ...exhausted, unusableForMs: UNRECOVERABLE_GRACE_MS }),
      true,
    )
  })

  it("does nothing for an unusable token when refresh can still recover", () => {
    assert.equal(
      shouldSignOutForDeadSession({ ...base, unusableForMs: UNRECOVERABLE_GRACE_MS * 10 }),
      false,
    )
  })
})
