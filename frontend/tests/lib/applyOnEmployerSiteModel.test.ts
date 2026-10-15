import assert from "node:assert/strict";
import test from "node:test";

import {
  applyEmployerSiteHelperCopy,
  applyEmployerSiteLabel,
  applyEmployerSiteNavigation,
  resolveApplyEmployerSiteStructural,
  withApplyOnEmployerSiteIntent,
  sanitizeJobPostingUrl,
  showGetExtensionLink,
  toDisplayState,
} from "@/lib/applyOnEmployerSiteModel";

test("state D when URL missing or invalid", () => {
  const missing = resolveApplyEmployerSiteStructural(null);
  assert.equal(missing.structural, "no-url");
  assert.equal(missing.href, null);
  assert.equal(toDisplayState(missing.structural, null), "D");
  assert.equal(applyEmployerSiteLabel("D"), null);

  const bad = resolveApplyEmployerSiteStructural("javascript:alert(1)");
  assert.equal(bad.structural, "no-url");
  assert.equal(bad.href, null);

  const jsHost = resolveApplyEmployerSiteStructural("javascript://boards.greenhouse.io/%0aalert(1)");
  assert.equal(jsHost.structural, "no-url");
  assert.equal(jsHost.href, null);
});

test("sanitizeJobPostingUrl rejects userinfo control chars and oversize", () => {
  assert.equal(
    sanitizeJobPostingUrl("https://user:pass@boards.greenhouse.io/jobs/1"),
    null,
  );
  assert.equal(
    sanitizeJobPostingUrl("https://boards.greenhouse.io/jobs/1\r\nX: 1"),
    null,
  );
  assert.equal(sanitizeJobPostingUrl("https://boards.greenhouse.io/" + "a".repeat(2100)), null);
});

test("state C off-allowlist with href", () => {
  const url = "https://jobs.smartrecruiters.com/acme/1";
  const resolved = resolveApplyEmployerSiteStructural(url);
  assert.equal(resolved.structural, "off-allowlist");
  assert.equal(resolved.href, url);
  assert.equal(toDisplayState(resolved.structural, true), "C");
  assert.equal(applyEmployerSiteLabel("C"), "Open job posting");
});

test("withApplyOnEmployerSiteIntent adds flintapply=apply query param", () => {
  const url = "https://boards.greenhouse.io/acme/jobs/1";
  const withIntent = withApplyOnEmployerSiteIntent(url);
  assert.match(withIntent, /flintapply=apply/);
  assert.equal(applyEmployerSiteNavigation(url).href, withIntent);
});

test("allowlisted URLs map to A/B by detection", () => {
  const url = "https://boards.greenhouse.io/acme/jobs/1";
  const resolved = resolveApplyEmployerSiteStructural(url);
  assert.equal(resolved.structural, "allowlisted");
  assert.equal(resolved.href, url);
  assert.equal(toDisplayState("allowlisted", true), "A");
  assert.equal(toDisplayState("allowlisted", null), "A");
  assert.equal(toDisplayState("allowlisted", false), "B");
  assert.equal(applyEmployerSiteLabel("A"), "Apply on employer site");
});

test("helper copy transitions from in-flight A to timeout B", () => {
  const inFlight = applyEmployerSiteHelperCopy({ state: "A", extensionDetected: null });
  assert.match(inFlight, /offers to autofill/);
  // Must name the mapped platforms and not over-promise on multi-step forms.
  assert.match(inFlight, /Greenhouse, Lever and Ashby/);
  assert.match(inFlight, /Workday still need manual review/);

  const timedOut = applyEmployerSiteHelperCopy({ state: "B", extensionDetected: false });
  assert.match(timedOut, /Install Flint Apply/);
  assert.notEqual(inFlight, timedOut);
  assert.equal(showGetExtensionLink({ state: "B", extensionDetected: false }), true);
});

test("state C shows extension link only when not detected", () => {
  assert.equal(showGetExtensionLink({ state: "C", extensionDetected: false }), true);
  assert.equal(showGetExtensionLink({ state: "C", extensionDetected: true }), false);
  assert.equal(showGetExtensionLink({ state: "C", extensionDetected: null }), false);
  assert.equal(showGetExtensionLink({ state: "A", extensionDetected: null }), false);
  assert.equal(showGetExtensionLink({ state: "D", extensionDetected: false }), true);
});

test("toDisplayState keeps C/D when extension not detected", () => {
  assert.equal(toDisplayState("off-allowlist", false), "C");
  assert.equal(toDisplayState("no-url", false), "D");
  assert.equal(applyEmployerSiteLabel("B"), "Apply on employer site");
});
