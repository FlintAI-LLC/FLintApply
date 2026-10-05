import { describe, it, before, after, afterEach } from "node:test";
import assert from "node:assert/strict";
import { getBillingPrices } from "@/lib/api";

let sessionPayload: Record<string, unknown> = {};
let lastAuth: string | undefined;
const originalFetch = globalThis.fetch;
const OriginalBroadcastChannel = globalThis.BroadcastChannel;

function hrefOf(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

function authFromInit(init?: RequestInit): string | undefined {
  const headers = init?.headers;
  if (!headers) return undefined;
  if (headers instanceof Headers) return headers.get("Authorization") ?? undefined;
  const record = headers as Record<string, string>;
  return record.Authorization;
}

before(() => {
  globalThis.BroadcastChannel = class {
    constructor(_name: string) {}
    postMessage(): void {}
    addEventListener(): void {}
    removeEventListener(): void {}
    close(): void {}
    dispatchEvent(): boolean {
      return false;
    }
  } as unknown as typeof BroadcastChannel;

  globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
    const href = hrefOf(input);
    if (href.includes("/api/auth/") || href.endsWith("/session")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => sessionPayload,
      } as unknown as Response);
    }
    lastAuth = authFromInit(init);
    return Promise.resolve({
      ok: true,
      status: 200,
      json: async () => ({ plans: [] }),
    } as unknown as Response);
  }) as typeof fetch;
});

afterEach(() => {
  sessionPayload = {};
  lastAuth = undefined;
});

after(() => {
  globalThis.fetch = originalFetch;
  globalThis.BroadcastChannel = OriginalBroadcastChannel;
});

describe("api request Authorization", () => {
  it("prefers live session token over stale init Authorization", async () => {
    sessionPayload = {
      backendAccessToken: "live-tok",
      backendExpiresAt: Date.now() + 60_000,
    };
    await getBillingPrices("stale-tok");
    assert.equal(lastAuth, "Bearer live-tok");
  });

  it("does not attach a dead session JWT when only init Authorization is stale", async () => {
    sessionPayload = {
      backendAccessToken: "dead-tok",
      backendExpiresAt: Date.now() - 1,
    };
    await getBillingPrices("stale-tok");
    assert.equal(lastAuth, "Bearer stale-tok");
  });
});
