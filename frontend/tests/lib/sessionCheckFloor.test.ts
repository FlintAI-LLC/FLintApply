import { describe, it } from "node:test"
import assert from "node:assert/strict"
import { SESSION_CHECK_FLOOR_MS, SessionCheckFloor } from "@/lib/sessionCheckFloor"

describe("SessionCheckFloor", () => {
  it("defaults to a 10 second floor", async () => {
    assert.equal(SESSION_CHECK_FLOOR_MS, 10_000)

    let clock = 0
    const floor = new SessionCheckFloor<string>(undefined, () => clock)
    let fetches = 0
    const fetcher = async () => {
      fetches += 1
      return "snapshot"
    }

    await floor.run("s1", fetcher)
    clock = 9_999
    await floor.run("s1", fetcher)
    assert.equal(fetches, 1)
    clock = 10_000
    await floor.run("s1", fetcher)
    assert.equal(fetches, 2)
  })

  it("keeps different users apart when the key includes the user", async () => {
    const floor = new SessionCheckFloor<string>(10_000, () => 1_000)
    let fetches = 0

    const a = await floor.run("userA:s1", async () => {
      fetches += 1
      return "A snapshot"
    })
    const b = await floor.run("userB:s1", async () => {
      fetches += 1
      return "B snapshot"
    })

    assert.equal(a, "A snapshot")
    assert.equal(b, "B snapshot")
    assert.equal(fetches, 2)
  })

  it("shares one request for repeats inside the window", async () => {
    let clock = 1_000
    const floor = new SessionCheckFloor<string>(10_000, () => clock)
    let fetches = 0
    const fetcher = async () => {
      fetches += 1
      return "snapshot"
    }

    await floor.run("s1", fetcher)
    clock += 9_999
    await floor.run("s1", fetcher)
    assert.equal(fetches, 1)
  })

  it("fetches again once the window has passed", async () => {
    let clock = 1_000
    const floor = new SessionCheckFloor<string>(10_000, () => clock)
    let fetches = 0
    const fetcher = async () => {
      fetches += 1
      return "snapshot"
    }

    await floor.run("s1", fetcher)
    clock += 10_000
    await floor.run("s1", fetcher)
    assert.equal(fetches, 2)
  })

  it("does not throttle a different session id", async () => {
    const floor = new SessionCheckFloor<string>(10_000, () => 1_000)
    let fetches = 0
    const fetcher = async () => {
      fetches += 1
      return "snapshot"
    }

    await floor.run("s1", fetcher)
    await floor.run("s2", fetcher)
    assert.equal(fetches, 2)
  })

  it("invalidate forces the next call through", async () => {
    const floor = new SessionCheckFloor<string>(10_000, () => 1_000)
    let fetches = 0
    const fetcher = async () => {
      fetches += 1
      return "snapshot"
    }

    await floor.run("s1", fetcher)
    floor.invalidate("s1")
    await floor.run("s1", fetcher)
    assert.equal(fetches, 2)
  })

  it("does not pin a failed request for the whole window", async () => {
    const floor = new SessionCheckFloor<string>(10_000, () => 1_000)
    let fetches = 0

    await assert.rejects(
      floor.run("s1", async () => {
        fetches += 1
        throw new Error("network")
      }),
    )
    // Let the cleanup handler run.
    await new Promise((resolve) => setImmediate(resolve))

    const value = await floor.run("s1", async () => {
      fetches += 1
      return "ok"
    })
    assert.equal(value, "ok")
    assert.equal(fetches, 2)
  })
})
