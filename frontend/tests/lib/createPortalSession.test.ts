import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const apiSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../../lib/api.ts"),
  "utf8",
);

describe("subscription management API client", () => {
  it("createPortalSession POSTs return_url and maps response url", () => {
    const fn = apiSource.slice(
      apiSource.indexOf("export async function createPortalSession"),
      apiSource.indexOf("export const DEFAULT_SUBSCRIPTION_PAUSE_DAYS"),
    );
    assert.match(fn, /body: JSON\.stringify\(\{ return_url \}\)/);
    assert.match(fn, /portal_url: data\.url/);
  });

  it("pauseSubscription sends days by default", () => {
    const fn = apiSource.slice(
      apiSource.indexOf("export async function pauseSubscription"),
      apiSource.indexOf("export async function unpauseSubscription"),
    );
    assert.match(fn, /DEFAULT_SUBSCRIPTION_PAUSE_DAYS/);
    assert.match(fn, /subscriptionPost\(token, "\/api\/subscriptions\/pause", body\)/);
  });

  it("cancel uses subscriptionPost with JSON body", () => {
    const helper = apiSource.slice(
      apiSource.indexOf("function subscriptionPost"),
      apiSource.indexOf("export async function cancelSubscription"),
    );
    assert.match(helper, /JSON\.stringify\(body\)/);
    const cancel = apiSource.slice(
      apiSource.indexOf("export async function cancelSubscription"),
      apiSource.indexOf("export async function resumeSubscription"),
    );
    assert.match(cancel, /subscriptionPost\(token, "\/api\/subscriptions\/cancel"\)/);
  });
});
