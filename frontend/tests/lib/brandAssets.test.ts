import assert from "node:assert/strict"
import { createHash } from "node:crypto"
import { existsSync, readFileSync } from "node:fs"
import { join } from "node:path"
import { describe, it } from "node:test"
const repoRoot = join(__dirname, "..", "..", "..")

function pngDimensions(buf: Buffer): { width: number; height: number } {
  return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) }
}
const brandDir = join(repoRoot, "frontend", "public", "brand")
const appDir = join(repoRoot, "frontend", "app")

describe("FlintApply brand assets", () => {
  it("ships light and dark wordmarks", () => {
    assert.ok(existsSync(join(brandDir, "flintapply-wordmark-light.png")))
    assert.ok(existsSync(join(brandDir, "flintapply-wordmark-dark.png")))
  })

  it("Open Graph image uses FlintApply dimensions (not legacy TalioCV file)", () => {
    const ogPath = join(appDir, "opengraph-image.png")
    const archivePath = join(brandDir, "archive", "talio-cv", "opengraph-image.png")
    const size = pngDimensions(readFileSync(ogPath))
    assert.equal(size.width, 1200)
    assert.equal(size.height, 630)
    const ogHash = createHash("sha256").update(readFileSync(ogPath)).digest("hex")
    const legacyHash = createHash("sha256").update(readFileSync(archivePath)).digest("hex")
    assert.notEqual(ogHash, legacyHash)
  })

  it("archives legacy TalioCV social assets", () => {
    const archive = join(brandDir, "archive", "talio-cv", "opengraph-image.png")
    assert.ok(existsSync(archive))
    assert.ok(existsSync(join(brandDir, "archive", "talio-cv", "icon.png")))
  })
})
