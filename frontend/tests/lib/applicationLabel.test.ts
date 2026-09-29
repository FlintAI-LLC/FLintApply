import test from "node:test";
import assert from "node:assert/strict";
import { formatApplicationLabel } from "../../lib/applicationLabel";

test("formatApplicationLabel joins company and title", () => {
  assert.equal(
    formatApplicationLabel("Mitratech", "Senior Software Engineer – In Test"),
    "Mitratech — Senior Software Engineer – In Test",
  );
});

test("formatApplicationLabel handles missing company", () => {
  assert.equal(formatApplicationLabel(null, "Staff Engineer"), "Staff Engineer");
});
