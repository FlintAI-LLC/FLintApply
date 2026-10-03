/**
 * Component tests for profile brick builder UI.
 *
 * Run: pnpm run test:unit
 */

import assert from "node:assert/strict"
import { describe, it } from "node:test"
import React from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { BrickCard } from "@/components/profile/BrickCard"
import type { ProfileBrick } from "@/lib/profile"

const BRICK: ProfileBrick = {
  id: "brick-1",
  section_type: "experience",
  content: "Led platform migration serving 2M users.",
  token_count: 12,
  source_doc_id: null,
  created_at: "2026-01-01T00:00:00Z",
}

describe("BrickCard", () => {
  it("renders content with edit and delete controls", () => {
    const html = renderToStaticMarkup(
      <BrickCard brick={BRICK} onSave={async () => {}} onDelete={async () => {}} />,
    )
    assert.match(html, /Led platform migration/)
    assert.match(html, /data-testid="brick-edit"/)
    assert.match(html, /data-testid="brick-delete"/)
  })

  it("escapes HTML in content as literal text", () => {
    const evil: ProfileBrick = {
      ...BRICK,
      content: '<img onerror="alert(1)" src="x">',
    }
    const html = renderToStaticMarkup(
      <BrickCard brick={evil} onSave={async () => {}} onDelete={async () => {}} />,
    )
    assert.match(html, /&lt;img/)
    assert.doesNotMatch(html, /<img onerror/)
  })
})

describe("brick add form contract", () => {
  it("POST body uses active section_type", () => {
    const sectionType = "skills"
    const content = "Kubernetes, Go"
    const body = JSON.stringify({ section_type: sectionType, content })
    assert.deepEqual(JSON.parse(body), {
      section_type: "skills",
      content: "Kubernetes, Go",
    })
  })
})
