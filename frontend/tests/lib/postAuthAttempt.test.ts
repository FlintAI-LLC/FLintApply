import { describe, it } from "node:test"
import assert from "node:assert/strict"
import { PostAuthAttemptGuard } from "@/lib/auth/postAuthAttempt"

interface FakeUser {
  onboarding_completed_at: string | null
}

function harness(fetchUser: (token: string) => Promise<FakeUser>) {
  const guard = new PostAuthAttemptGuard<FakeUser>()
  const calls = { fetchMe: 0, signOut: 0, redirect: 0 }
  const counted = async (token: string) => {
    calls.fetchMe += 1
    return fetchUser(token)
  }
  const verify = (token: string) =>
    guard.verify(token, counted, {
      onUser: () => {
        calls.redirect += 1
      },
      onStale: () => {
        calls.signOut += 1
      },
    })
  return { guard, calls, verify }
}

describe("PostAuthAttemptGuard", () => {
  it("one 401 produces exactly one fetchMe and one signOut, however often the effect re-runs", async () => {
    const { calls, verify } = harness(async () => {
      throw new Error("Access token expired")
    })

    for (let rerun = 0; rerun < 25; rerun += 1) {
      await verify("expired-token")
    }

    assert.equal(calls.fetchMe, 1)
    assert.equal(calls.signOut, 1)
    assert.equal(calls.redirect, 0)
  })

  it("overlapping calls for one token share a single attempt", async () => {
    let release: () => void = () => {}
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    const { calls, verify } = harness(async () => {
      await gate
      throw new Error("Access token expired")
    })

    const overlapping = Promise.all([verify("t"), verify("t"), verify("t")])
    release()
    await overlapping

    assert.equal(calls.fetchMe, 1)
    assert.equal(calls.signOut, 1)
  })

  it("a new token gets its own single attempt", async () => {
    const { calls, verify } = harness(async () => {
      throw new Error("Invalid access token")
    })

    await verify("token-a")
    await verify("token-a")
    await verify("token-b")
    await verify("token-b")

    assert.equal(calls.fetchMe, 2)
    assert.equal(calls.signOut, 2)
  })

  it("redirects once on success and ignores later re-runs", async () => {
    const { calls, verify } = harness(async () => ({ onboarding_completed_at: "2026-01-01" }))

    await verify("live-token")
    await verify("live-token")
    await verify("rotated-token")

    assert.equal(calls.redirect, 1)
    assert.equal(calls.signOut, 0)
    assert.equal(calls.fetchMe, 1)
  })

  it("does not sign out on a non-auth failure", async () => {
    const { calls, verify } = harness(async () => {
      throw new Error("HTTP 503")
    })

    await verify("token")
    assert.equal(calls.signOut, 0)
    assert.equal(calls.redirect, 0)
  })

  it("reset re-arms the guard after the user signs out", async () => {
    const { guard, calls, verify } = harness(async () => {
      throw new Error("Access token expired")
    })

    await verify("token")
    guard.reset()
    await verify("token")

    assert.equal(calls.fetchMe, 2)
    assert.equal(calls.signOut, 2)
  })
})
