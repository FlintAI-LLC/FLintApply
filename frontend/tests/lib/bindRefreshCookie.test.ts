import { afterEach, beforeEach, describe, it } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import path from "node:path"
import {
  MAX_BIND_ATTEMPTS,
  bindRefreshCookie,
  resetBindRefreshCookie,
  shouldBindRefreshCookie,
} from "@/lib/auth/bindRefreshCookie"

const originalFetch = globalThis.fetch

interface Call {
  url: string
  init: RequestInit
}
let calls: Call[] = []

function stubFetch(respond: () => Response | Promise<Response>): void {
  globalThis.fetch = (async (url: string, init: RequestInit) => {
    calls.push({ url, init })
    return respond()
  }) as typeof fetch
}

describe("bindRefreshCookie", () => {
  beforeEach(() => {
    resetBindRefreshCookie()
    calls = []
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    resetBindRefreshCookie()
  })

  it("posts once with credentials and the bearer token", async () => {
    stubFetch(() => new Response("{}", { status: 200 }))

    assert.equal(await bindRefreshCookie("user-1", "tok-1"), true)

    assert.equal(calls.length, 1)
    assert.match(calls[0].url, /\/api\/auth\/refresh-cookie$/)
    assert.equal(calls[0].init.method, "POST")
    assert.equal(calls[0].init.credentials, "include")
    assert.deepEqual(calls[0].init.headers, { Authorization: "Bearer tok-1" })
  })

  it("fires at most once per tab however often it is asked", async () => {
    stubFetch(() => new Response("{}", { status: 200 }))

    await Promise.all([
      bindRefreshCookie("user-1", "tok-1"),
      bindRefreshCookie("user-1", "tok-1"),
      bindRefreshCookie("user-1", "tok-1"),
    ])
    await bindRefreshCookie("user-1", "tok-2-after-rotation")
    await bindRefreshCookie("user-1", "tok-3-after-rotation")

    assert.equal(calls.length, 1)
  })

  it("binds again for a different user in the same tab", async () => {
    stubFetch(() => new Response("{}", { status: 200 }))

    await bindRefreshCookie("user-1", "tok-1")
    await bindRefreshCookie("user-2", "tok-2")

    assert.equal(calls.length, 2)
  })

  it("caps failed attempts instead of looping", async () => {
    stubFetch(() => new Response("{}", { status: 500 }))

    for (let attempt = 0; attempt < MAX_BIND_ATTEMPTS + 5; attempt += 1) {
      assert.equal(await bindRefreshCookie("user-1", `tok-${attempt}`), false)
    }

    assert.equal(calls.length, MAX_BIND_ATTEMPTS)
  })

  it("treats a network error as a failed attempt, not a crash", async () => {
    globalThis.fetch = (async () => {
      calls.push({ url: "", init: {} })
      throw new TypeError("Failed to fetch")
    }) as typeof fetch

    assert.equal(await bindRefreshCookie("user-1", "tok"), false)
    assert.equal(calls.length, 1)
  })

  it("a success after one failure still ends the attempts", async () => {
    let status = 500
    stubFetch(() => new Response("{}", { status }))

    await bindRefreshCookie("user-1", "tok-a")
    status = 200
    assert.equal(await bindRefreshCookie("user-1", "tok-b"), true)
    await bindRefreshCookie("user-1", "tok-c")

    assert.equal(calls.length, 2)
  })

  it("failures for one user never block another user in the same tab", async () => {
    stubFetch(() => new Response("{}", { status: 409 }))
    for (let attempt = 0; attempt < MAX_BIND_ATTEMPTS + 2; attempt += 1) {
      await bindRefreshCookie("user-1", "tok")
    }
    assert.equal(calls.length, MAX_BIND_ATTEMPTS)

    stubFetch(() => new Response("{}", { status: 200 }))
    assert.equal(await bindRefreshCookie("user-2", "tok"), true)
    assert.equal(calls.length, MAX_BIND_ATTEMPTS + 1)
  })

  it("never posts without an access token", async () => {
    stubFetch(() => new Response("{}", { status: 200 }))

    assert.equal(await bindRefreshCookie("user-1", ""), false)
    assert.equal(await bindRefreshCookie("user-1", "   "), false)
    assert.equal(calls.length, 0)
  })

  it("reset lets a later sign-in in the same tab bind again", async () => {
    stubFetch(() => new Response("{}", { status: 200 }))

    await bindRefreshCookie("user-1", "tok")
    resetBindRefreshCookie()
    await bindRefreshCookie("user-1", "tok")

    assert.equal(calls.length, 2)
  })
})

describe("shouldBindRefreshCookie", () => {
  const live = { status: "authenticated" as const, token: "tok", userId: "u1" }

  it("binds only when authenticated with a live token and a user id", () => {
    assert.equal(shouldBindRefreshCookie(live), true)
  })

  it("does not bind while loading or signed out", () => {
    assert.equal(shouldBindRefreshCookie({ ...live, status: "loading" }), false)
    assert.equal(shouldBindRefreshCookie({ ...live, status: "unauthenticated" }), false)
  })

  it("does not bind without a usable token or user id", () => {
    assert.equal(shouldBindRefreshCookie({ ...live, token: undefined }), false)
    assert.equal(shouldBindRefreshCookie({ ...live, token: "" }), false)
    assert.equal(shouldBindRefreshCookie({ ...live, token: "  " }), false)
    assert.equal(shouldBindRefreshCookie({ ...live, userId: undefined }), false)
  })
})

describe("RefreshCookieBinder wiring", () => {
  const read = (relative: string) =>
    readFileSync(path.join(process.cwd(), relative), "utf8")

  it("is mounted beside BackendTokenRefresh", () => {
    assert.match(
      read("components/nav/SessionProvider.tsx"),
      /<BackendTokenRefresh \/>\s*<RefreshCookieBinder \/>/,
    )
  })

  it("gates on the live token, and resets when signed out", () => {
    const source = read("components/nav/RefreshCookieBinder.tsx")
    assert.match(source, /liveBackendAccessToken\(session\)/)
    assert.match(source, /shouldBindRefreshCookie\(\{ status, token, userId \}\)/)
    assert.match(source, /void bindRefreshCookie\(userId, token\)/)
    assert.match(
      source,
      /status === "unauthenticated"\) \{\s*resetBindRefreshCookie\(\)/,
    )
  })
})
