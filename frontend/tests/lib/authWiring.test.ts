import { describe, it } from "node:test"
import assert from "node:assert/strict"
import { readFileSync, readdirSync, statSync } from "node:fs"
import path from "node:path"

/**
 * The repo has no DOM renderer, so these pin the React wiring that the pure
 * unit tests cannot reach. They exist to fail if a fix is reverted.
 */

const ROOT = process.cwd()
const read = (relative: string) => readFileSync(path.join(ROOT, relative), "utf8")

function sourceFiles(dir: string): string[] {
  const out: string[] = []
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name === ".next" || name === "tests") continue
    const full = path.join(dir, name)
    if (statSync(full).isDirectory()) out.push(...sourceFiles(full))
    else if (/\.(ts|tsx)$/.test(name)) out.push(full)
  }
  return out
}

describe("auth wiring contracts", () => {
  it("the /auth redirect effect verifies the live token with narrow deps", () => {
    const source = read("app/auth/page.tsx")
    assert.match(source, /postAuthGuard\.verify\(liveToken,/)
    assert.doesNotMatch(source, /fetchMe\(session\??\.backendAccessToken/)
    assert.match(
      source,
      /\}, \[status, liveToken, hasBackendToken, sessionError\]\)/,
    )
  })

  it("the session hydration effect runs on [sessionId] only, through the floor", () => {
    const source = read("app/session/[id]/page.tsx")
    const effect = source.match(
      /sessionCheckFloor\s*\.run\([\s\S]*?\n\s*\}, \[([^\]]*)\]\);/,
    )
    assert.ok(effect, "hydration effect not found")
    assert.equal(effect[1].trim(), "sessionId")
    assert.match(source, /^const sessionCheckFloor = new SessionCheckFloor/m)
  })

  it("only BackendTokenRefresh imports refreshBackendSession", () => {
    const importer =
      /import\s*\{[^}]*\brefreshBackendSession(?:IfNeeded)?\b[^}]*\}\s*from\s*["']@\/lib\/auth\/refreshBackendSession["']/
    const offenders = sourceFiles(ROOT)
      .filter((file) => importer.test(readFileSync(file, "utf8")))
      .map((file) => path.relative(ROOT, file))
    assert.deepEqual(offenders, ["components/nav/BackendTokenRefresh.tsx"])
  })

  it("useEntitlement waits on live backend tokens, not raw backendAccessToken", () => {
    const source = read("hooks/useEntitlement.ts")
    assert.match(source, /useLiveBackendAccessToken/)
    assert.doesNotMatch(source, /session\?\.backendAccessToken/)
  })

  it("UsageWidget does not trigger a refresh on 401", () => {
    const source = read("components/nav/UsageWidget.tsx")
    assert.doesNotMatch(source, /refreshBackendSession|requestBackendSessionRefresh/)
  })

  it("BackendTokenRefresh recovery effect does not depend on the whole session", () => {
    const source = read("components/nav/BackendTokenRefresh.tsx")
    assert.match(source, /\}, \[status, session\?\.error, session\?\.backendExpiresAt\]\)/)
    assert.match(source, /\}, \[status\]\)/)
  })
})
