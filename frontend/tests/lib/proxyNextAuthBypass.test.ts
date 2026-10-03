import { describe, it } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import path from "node:path"

describe("proxy NextAuth bypass", () => {
  it("never runs onboarding redirects for any /api/auth/ route", () => {
    const source = readFileSync(
      path.join(process.cwd(), "proxy.ts"),
      "utf8",
    )
    assert.match(
      source,
      /if \(pathname\.startsWith\("\/api\/auth\/"\)\)/,
      "expected early return for all NextAuth API routes",
    )
    assert.doesNotMatch(
      source,
      /!pathname\.startsWith\("\/api\/auth\/signin"\)/,
      "signin routes must not be excluded from the JSON bypass",
    )
  })
})
