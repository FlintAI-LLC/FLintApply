import { describe, it } from "node:test"
import assert from "node:assert/strict"
import { safeReturnPath } from "@/lib/auth/returnUrl"

describe("safeReturnPath", () => {
  it("allows single-slash internal paths", () => {
    assert.equal(safeReturnPath("/jobs"), "/jobs")
    assert.equal(safeReturnPath("/dashboard?foo=bar"), "/dashboard?foo=bar")
  })

  it("rejects protocol-relative URLs", () => {
    assert.equal(safeReturnPath("//evil.example"), "/dashboard")
    assert.equal(safeReturnPath("/\\evil.example"), "/dashboard")
  })

  it("rejects absolute URLs and other schemes", () => {
    assert.equal(safeReturnPath("https://evil.example/attack"), "/dashboard")
    assert.equal(safeReturnPath("javascript:alert(1)"), "/dashboard")
    assert.equal(safeReturnPath("data:text/html,foo"), "/dashboard")
  })

  it("falls back on empty or missing input", () => {
    assert.equal(safeReturnPath(null), "/dashboard")
    assert.equal(safeReturnPath(""), "/dashboard")
    assert.equal(safeReturnPath("   "), "/dashboard")
    assert.equal(safeReturnPath(null, "/jobs"), "/jobs")
  })
})
