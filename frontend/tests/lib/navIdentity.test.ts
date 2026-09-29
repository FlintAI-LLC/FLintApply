import { describe, it } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import path from "node:path"
import { shouldShowUserMenu } from "@/lib/auth/navIdentity"

describe("shouldShowUserMenu", () => {
  it("stays visible while the embedded API token is cleared and restored", () => {
    const rotation = [
      { backendAccessToken: "old" },
      { backendAccessToken: undefined, error: "TokenExpired" },
      { backendAccessToken: undefined },
      { backendAccessToken: "new" },
    ]

    for (const session of rotation) {
      assert.equal(shouldShowUserMenu("authenticated", session, false), true)
    }
  })

  it("hides the menu when signed out, loading, without a session, or dead", () => {
    const session = { backendAccessToken: "tok" }
    assert.equal(shouldShowUserMenu("unauthenticated", null, false), false)
    assert.equal(shouldShowUserMenu("loading", undefined, false), false)
    assert.equal(shouldShowUserMenu("authenticated", null, false), false)
    assert.equal(shouldShowUserMenu("authenticated", session, true), false)
  })

  it("NavBar assigns showUserMenu from the helper alone", () => {
    const source = readFileSync(
      path.join(process.cwd(), "components/nav/NavBar.tsx"),
      "utf8",
    )
    const assignment = source.match(/const showUserMenu =([^\n]*(?:\n\s+[^\n]*)*?);?\n\s*useEffect/)
    assert.ok(assignment, "showUserMenu assignment not found")
    assert.equal(
      assignment[1].replace(/\s+/g, " ").trim(),
      "shouldShowUserMenu(status, session, isSessionDead())",
    )
  })
})
