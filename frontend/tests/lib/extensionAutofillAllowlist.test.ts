import assert from "node:assert/strict";
import test from "node:test";

import { isAutofillAllowlistedUrl } from "@/lib/extensionAutofillAllowlist";

test("allowlisted ATS hosts", () => {
  assert.equal(isAutofillAllowlistedUrl("https://boards.greenhouse.io/acme/jobs/1"), true);
  assert.equal(isAutofillAllowlistedUrl("https://my.greenhouse.io/jobs"), true);
  assert.equal(isAutofillAllowlistedUrl("https://jobs.lever.co/acme/abc"), true);
  assert.equal(isAutofillAllowlistedUrl("https://jobs.ashbyhq.com/acme/abc"), true);
  assert.equal(isAutofillAllowlistedUrl("https://acme.myworkdayjobs.com/en-US/careers"), true);
  assert.equal(isAutofillAllowlistedUrl("https://careers.icims.com/jobs/1"), true);
  assert.equal(isAutofillAllowlistedUrl("https://acme.ukg.net/careers"), true);
  assert.equal(isAutofillAllowlistedUrl("https://jobright.ai/j/1"), true);
  assert.equal(isAutofillAllowlistedUrl("https://www.jobright.ai/j/1"), true);
  assert.equal(isAutofillAllowlistedUrl("https://linkedin.com/jobs/view/123"), true);
});

test("rejects off-allowlist and unsafe URLs", () => {
  assert.equal(isAutofillAllowlistedUrl("https://jobs.smartrecruiters.com/acme/1"), false);
  assert.equal(isAutofillAllowlistedUrl("https://indeed.com/viewjob"), false);
  assert.equal(isAutofillAllowlistedUrl("https://www.linkedin.com/feed/"), false);
  assert.equal(isAutofillAllowlistedUrl("https://example.com/jobs/1"), false);
  assert.equal(isAutofillAllowlistedUrl("javascript:alert(1)"), false);
  assert.equal(isAutofillAllowlistedUrl("javascript://boards.greenhouse.io/%0aalert(1)"), false);
  assert.equal(isAutofillAllowlistedUrl("ftp://boards.greenhouse.io/jobs/1"), false);
  assert.equal(isAutofillAllowlistedUrl("https://boards.greenhouse.io.evil.com/jobs/1"), false);
  assert.equal(isAutofillAllowlistedUrl("https://www.linkedin.com/jobsfoo"), false);
});
