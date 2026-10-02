import assert from "node:assert/strict";
import test from "node:test";

test("draft review API paths are session-scoped", () => {
  const sessionId = "sess-abc";
  assert.equal(
    `/api/sessions/${sessionId}/draft-review`,
    "/api/sessions/sess-abc/draft-review",
  );
  assert.equal(
    `/api/sessions/${sessionId}/draft/bullets/experience:0:1`,
    "/api/sessions/sess-abc/draft/bullets/experience:0:1",
  );
});
