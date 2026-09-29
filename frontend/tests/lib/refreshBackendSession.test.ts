import { afterEach, beforeEach, describe, it } from "node:test"
import assert from "node:assert/strict"
import {
  BACKEND_REFRESH_REQUEST_EVENT,
  MAX_CONSECUTIVE_FAILURES,
  REFRESH_401_BLOCK_MS,
  REFRESH_429_BLOCK_MS,
  REFRESH_REQUEST_MIN_INTERVAL_MS,
  SESSION_DEAD_EVENT,
  isRefreshRateLimited,
  isSessionDead,
  refreshBackendSession,
  refreshUnrecoverable,
  requestBackendSessionRefresh,
  resetRefreshState,
} from "@/lib/auth/refreshBackendSession"

const originalFetch = globalThis.fetch
const realNow = Date.now
const globalWithWindow = globalThis as unknown as { window?: unknown }

let fetchCalls = 0
let updateCalls = 0
let clock = 1_000_000
let dispatched: string[] = []

function stubFetch(status: number, body: unknown = {}): void {
  globalThis.fetch = (async () => {
    fetchCalls += 1
    return new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    })
  }) as typeof fetch
}

function stubFetchNetworkError(): void {
  globalThis.fetch = (async () => {
    fetchCalls += 1
    throw new TypeError("Failed to fetch")
  }) as typeof fetch
}

const update = async () => {
  updateCalls += 1
  return null
}

const OK_BODY = {
  access_token: "tok",
  expires_in: 900,
  user: { id: "u1" },
}

async function failTimes(times: number): Promise<void> {
  for (let attempt = 0; attempt < times; attempt += 1) {
    await refreshBackendSession(update)
  }
}

describe("refreshBackendSession failure handling", () => {
  beforeEach(() => {
    resetRefreshState()
    fetchCalls = 0
    updateCalls = 0
    clock = 1_000_000
    dispatched = []
    Date.now = () => clock
    globalWithWindow.window = {
      dispatchEvent: (event: Event) => {
        dispatched.push(event.type)
        return true
      },
    }
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    Date.now = realNow
    delete globalWithWindow.window
  })

  it("trips the cooldown after 3 consecutive failures and never fires a 4th", async () => {
    stubFetch(500, { detail: "boom" })

    for (let attempt = 1; attempt < MAX_CONSECUTIVE_FAILURES; attempt += 1) {
      await refreshBackendSession(update)
      assert.equal(isRefreshRateLimited(), false, `not limited after attempt ${attempt}`)
    }
    await refreshBackendSession(update)
    assert.equal(fetchCalls, 3)
    assert.equal(isRefreshRateLimited(), true)

    assert.equal(await refreshBackendSession(update), false)
    assert.equal(fetchCalls, 3, "fourth attempt must not reach the network")
    assert.equal(updateCalls, 0)
  })

  it("counts network errors (no HTTP status) toward the cooldown", async () => {
    stubFetchNetworkError()
    await failTimes(3)
    assert.equal(isRefreshRateLimited(), true)

    await refreshBackendSession(update)
    assert.equal(fetchCalls, 3)
  })

  it("does not cool down after only two failures", async () => {
    stubFetch(500)
    await failTimes(2)
    assert.equal(isRefreshRateLimited(), false)
    assert.equal(refreshUnrecoverable(), false)
  })

  it("a success resets the failure counter", async () => {
    stubFetch(500)
    await failTimes(2)

    stubFetch(200, OK_BODY)
    assert.equal(await refreshBackendSession(update), true)
    assert.equal(updateCalls, 1)

    stubFetch(500)
    await failTimes(2)
    assert.equal(isRefreshRateLimited(), false, "counter restarted after success")
  })

  it("gives a fresh failure budget after the cooldown instead of re-tripping on one attempt", async () => {
    stubFetch(500)
    await failTimes(3)
    assert.equal(isRefreshRateLimited(), true)

    clock += REFRESH_401_BLOCK_MS
    await refreshBackendSession(update)
    assert.equal(isRefreshRateLimited(), false, "one failure after cooldown must not re-block")
    assert.equal(fetchCalls, 4)
  })

  it("repeated 5xx marks refresh unrecoverable without marking the cookie dead", async () => {
    stubFetch(503)
    await failTimes(3)
    assert.equal(refreshUnrecoverable(), true)
    assert.equal(isSessionDead(), false)
  })

  it("a single 401 marks the session dead and blocks further attempts", async () => {
    stubFetch(401, { detail: { code: "missing_refresh_token" } })

    assert.equal(isSessionDead(), false)
    assert.equal(await refreshBackendSession(update), false)
    assert.equal(isSessionDead(), true)
    assert.equal(refreshUnrecoverable(), true)
    assert.equal(isRefreshRateLimited(), true)

    assert.equal(await refreshBackendSession(update), false)
    assert.equal(await refreshBackendSession(update), false)
    assert.equal(fetchCalls, 1, "exactly one 401 per cooldown")
  })

  it("holds the 401 cooldown for exactly REFRESH_401_BLOCK_MS", async () => {
    stubFetch(401)
    await refreshBackendSession(update)
    assert.equal(fetchCalls, 1)

    clock += REFRESH_401_BLOCK_MS - 1
    await refreshBackendSession(update)
    assert.equal(fetchCalls, 1, "still blocked 1ms before the window ends")

    clock += 1
    stubFetch(200, OK_BODY)
    assert.equal(await refreshBackendSession(update), true)
    assert.equal(fetchCalls, 2)
    assert.equal(isSessionDead(), false, "success clears the dead flag")
    assert.equal(refreshUnrecoverable(), false)
  })

  it("dispatches SESSION_DEAD_EVENT once for a 401 and not for blocked retries", async () => {
    stubFetch(401)
    await refreshBackendSession(update)
    await refreshBackendSession(update)
    await refreshBackendSession(update)

    assert.deepEqual(dispatched, [SESSION_DEAD_EVENT])
  })

  it("a 429 cools down for 60s without marking the session dead or unrecoverable", async () => {
    stubFetch(429)
    await refreshBackendSession(update)

    assert.equal(isRefreshRateLimited(), true)
    assert.equal(isSessionDead(), false)
    assert.equal(refreshUnrecoverable(), false)
    assert.deepEqual(dispatched, [])

    await refreshBackendSession(update)
    assert.equal(fetchCalls, 1)

    clock += REFRESH_429_BLOCK_MS - 1
    await refreshBackendSession(update)
    assert.equal(fetchCalls, 1)

    clock += 1
    await refreshBackendSession(update)
    assert.equal(fetchCalls, 2)
  })

  it("repeated 429s never mark refresh unrecoverable", async () => {
    stubFetch(429)
    for (let attempt = 0; attempt < MAX_CONSECUTIVE_FAILURES; attempt += 1) {
      clock += REFRESH_429_BLOCK_MS
      await refreshBackendSession(update)
    }
    assert.equal(refreshUnrecoverable(), false)
  })

  it("shares one request between concurrent callers", async () => {
    let release: () => void = () => {}
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    globalThis.fetch = (async () => {
      fetchCalls += 1
      await gate
      return new Response(JSON.stringify(OK_BODY), { status: 200 })
    }) as typeof fetch

    const callers = Promise.all([
      refreshBackendSession(update),
      refreshBackendSession(update),
      refreshBackendSession(update),
    ])
    release()

    assert.deepEqual(await callers, [true, true, true])
    assert.equal(fetchCalls, 1)
    assert.equal(updateCalls, 1)
  })

  it("resetRefreshState clears every verdict for the next user", async () => {
    stubFetch(401)
    await refreshBackendSession(update)
    assert.equal(isSessionDead(), true)

    resetRefreshState()
    assert.equal(isSessionDead(), false)
    assert.equal(refreshUnrecoverable(), false)
    assert.equal(isRefreshRateLimited(), false)
  })
})

describe("requestBackendSessionRefresh", () => {
  beforeEach(() => {
    resetRefreshState()
    clock = 1_000_000
    dispatched = []
    Date.now = () => clock
    globalWithWindow.window = {
      dispatchEvent: (event: Event) => {
        dispatched.push(event.type)
        return true
      },
    }
  })

  afterEach(() => {
    Date.now = realNow
    delete globalWithWindow.window
  })

  it("throttles bursts to one event per interval", () => {
    requestBackendSessionRefresh()
    requestBackendSessionRefresh()
    requestBackendSessionRefresh()
    assert.deepEqual(dispatched, [BACKEND_REFRESH_REQUEST_EVENT])

    clock += REFRESH_REQUEST_MIN_INTERVAL_MS - 1
    requestBackendSessionRefresh()
    assert.equal(dispatched.length, 1)

    clock += 1
    requestBackendSessionRefresh()
    assert.equal(dispatched.length, 2)
  })
})
