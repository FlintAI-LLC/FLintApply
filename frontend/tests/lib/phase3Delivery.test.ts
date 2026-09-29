import { describe, it } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import path from "node:path"
import type { TailoredResumeOutput } from "@/lib/api"
import {
  CREDIT_RETURNED_NOTE,
  KEPT_PRIOR_NOTE,
  findKeptPriorNote,
  hasUsableSkills,
  resolvePhase3Delivery,
} from "@/lib/phase3Delivery"

function resume(overrides: Partial<TailoredResumeOutput> = {}): TailoredResumeOutput {
  return {
    contact: {},
    summary: "Summary",
    skills: ["Languages: Python"],
    experience: [
      { title: "Engineer", company: "Acme", dates: "2020", bullets: ["Owned the API."] },
    ],
    projects: [],
    education: [],
    certifications: [],
    rewrite_notes: [],
    metrics_needed: [],
    ...overrides,
  } as TailoredResumeOutput
}

describe("resolvePhase3Delivery", () => {
  it("trusts the server when it kept the prior resume", () => {
    const kept = resume({ rewrite_notes: [KEPT_PRIOR_NOTE + CREDIT_RETURNED_NOTE] })
    const result = resolvePhase3Delivery({
      output: kept,
      priorKept: true,
      creditRefunded: true,
      priorSnapshot: resume({ summary: "Other" }),
    })
    assert.equal(result.tailored, kept)
    assert.equal(result.restoredFromSnapshot, false)
  })

  it("passes a healthy regenerate through untouched", () => {
    const fresh = resume({ summary: "Fresh", phase3_delivery: "llm" })
    const result = resolvePhase3Delivery({
      output: fresh,
      priorKept: false,
      creditRefunded: false,
      priorSnapshot: resume(),
    })
    assert.equal(result.tailored, fresh)
    assert.equal(result.restoredFromSnapshot, false)
  })

  it("restores the snapshot when the server delivered a fallback tree", () => {
    const fallback = resume({ skills: [], phase3_delivery: "deterministic_fallback" })
    const snapshot = resume({ summary: "Mine" })
    const result = resolvePhase3Delivery({
      output: fallback,
      priorKept: false,
      creditRefunded: false,
      priorSnapshot: snapshot,
    })
    assert.equal(result.restoredFromSnapshot, true)
    assert.equal(result.tailored.summary, "Mine")
    assert.deepEqual(result.tailored.skills, snapshot.skills)
    assert.equal(result.tailored.phase3_delivery, "llm")
    assert.deepEqual(result.tailored.rewrite_notes, [KEPT_PRIOR_NOTE])
  })

  it("only claims a returned credit when the server confirmed the refund", () => {
    const fallback = resume({ phase3_delivery: "deterministic_fallback" })
    const returned = resolvePhase3Delivery({
      output: fallback,
      creditRefunded: true,
      priorSnapshot: resume(),
    })
    assert.deepEqual(returned.tailored.rewrite_notes, [KEPT_PRIOR_NOTE + CREDIT_RETURNED_NOTE])
    const charged = resolvePhase3Delivery({
      output: fallback,
      creditRefunded: false,
      priorSnapshot: resume(),
    })
    assert.deepEqual(charged.tailored.rewrite_notes, [KEPT_PRIOR_NOTE])
    const unknown = resolvePhase3Delivery({
      output: fallback,
      priorSnapshot: resume(),
    })
    assert.deepEqual(unknown.tailored.rewrite_notes, [KEPT_PRIOR_NOTE])
    const replayWithoutFlags = resolvePhase3Delivery({
      output: resume({ phase3_delivery: "llm" }),
      priorSnapshot: resume({ summary: "Older" }),
    })
    assert.equal(replayWithoutFlags.restoredFromSnapshot, false)
  })

  it("never leaves Skills empty when the previous resume had skills", () => {
    const noSkills = resume({ skills: [], phase3_delivery: "llm" })
    const result = resolvePhase3Delivery({
      output: noSkills,
      creditRefunded: false,
      priorSnapshot: resume(),
    })
    assert.equal(hasUsableSkills(result.tailored), true)
    assert.equal(result.restoredFromSnapshot, true)
  })

  it("keeps the fallback tree when there is nothing better to show", () => {
    const fallback = resume({ phase3_delivery: "deterministic_fallback" })
    for (const snapshot of [null, resume({ experience: [] })]) {
      const result = resolvePhase3Delivery({
        output: fallback,
        creditRefunded: false,
        priorSnapshot: snapshot,
      })
      assert.equal(result.tailored, fallback)
      assert.equal(result.restoredFromSnapshot, false)
    }
  })

  it("does not restore over an output whose skills are legitimately empty", () => {
    const empty = resume({ skills: [], phase3_delivery: "llm" })
    const result = resolvePhase3Delivery({
      output: empty,
      creditRefunded: false,
      priorSnapshot: resume({ skills: [] }),
    })
    assert.equal(result.tailored, empty)
  })

  it("treats whitespace-only skills as empty", () => {
    assert.equal(hasUsableSkills(resume({ skills: ["  ", ""] })), false)
  })
})

describe("session page wiring", () => {
  const source = readFileSync(
    path.join(process.cwd(), "app/session/[id]/page.tsx"),
    "utf8",
  )
  const resolveCall = source.slice(
    source.indexOf("resolvePhase3Delivery({"),
    source.indexOf("requestBackendSessionRefresh();", source.indexOf("resolvePhase3Delivery({")),
  )

  it("passes the server flags into the delivery policy", () => {
    assert.match(resolveCall, /priorKept: lastEvent\.prior_kept/)
    assert.match(resolveCall, /creditRefunded: lastEvent\.credit_refunded/)
  })

  it("reads the snapshot before clearing it", () => {
    const snapshotAt = resolveCall.indexOf("priorSnapshot: regenPriorRef.current")
    const clearedAt = resolveCall.indexOf("regenPriorRef.current = null")
    assert.ok(snapshotAt >= 0)
    assert.ok(clearedAt > snapshotAt)
  })

  it("never falls back to the partial-overwritten backup for the snapshot", () => {
    assert.doesNotMatch(source, /priorSnapshot: regenPriorRef\.current \?\? tailoredBackupRef/)
  })

  it("assigns the snapshot from the backup in exactly one place", () => {
    const assignments = source.match(/regenPriorRef\.current = tailoredBackupRef\.current/g) ?? []
    assert.equal(assignments.length, 1)
  })

  it("does not touch the snapshot from the partial or generic apply paths", () => {
    const applyBody = source.slice(
      source.indexOf("const applyPhaseOutputByNumber"),
      source.indexOf("const hydrateFromSession"),
    )
    assert.doesNotMatch(applyBody, /regenPriorRef/)
    const partialBranch = source.slice(
      source.indexOf('lastEvent.event === "partial"'),
      source.indexOf('lastEvent.event === "cost_estimate"'),
    )
    assert.doesNotMatch(partialBranch, /regenPriorRef/)
  })

  it("snapshots the resume before a forced regenerate clears it", () => {
    assert.match(source, /regenPriorRef\.current = tailoredBackupRef\.current;\s*setTailored\(null\)/)
  })

  it("clears a stale snapshot when a non-forced phase 3 run starts", () => {
    assert.match(source, /\} else if \(phase === 3\) \{\s*regenPriorRef\.current = null;/)
  })

  it("refreshes the credit display in the phase 3 done branch", () => {
    const start = source.indexOf("resolvePhase3Delivery({")
    assert.ok(start >= 0)
    const tail = source.slice(start, start + 1500)
    assert.match(tail, /requestBackendSessionRefresh\(\)/)
  })

  it("persists a client-side restore back to the server", () => {
    assert.match(
      source,
      /restoredFromSnapshot[\s\S]{0,120}saveTailoredResume\(sessionId, resolved\.tailored\)/,
    )
  })
})

describe("kept-prior note visibility", () => {
  const editor = readFileSync(
    path.join(process.cwd(), "components/session/TailoredEditor.tsx"),
    "utf8",
  )

  it("finds the note including the credit suffix", () => {
    assert.equal(
      findKeptPriorNote(["other", KEPT_PRIOR_NOTE + CREDIT_RETURNED_NOTE]),
      KEPT_PRIOR_NOTE + CREDIT_RETURNED_NOTE,
    )
    assert.equal(findKeptPriorNote(["Removed unverified metric"]), null)
  })

  it("renders a dedicated banner without needing the notes toggle", () => {
    assert.match(editor, /keptPriorNote !== null && \(\s*<div[^>]*data-testid="kept-prior-banner"/)
    assert.match(editor, /\{keptPriorNote\}/)
  })

  it("expands the notes panel by default when the note is present", () => {
    assert.match(editor, /findKeptPriorNote\(initial\.rewrite_notes\) !== null/)
  })
})
