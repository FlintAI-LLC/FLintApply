import { describe, it, afterEach } from "node:test";
import assert from "node:assert/strict";

import {
  CAREER_WATCH_MAX_KEYWORDS,
  getCareerWatchLimits,
  mergeCommaKeywords,
  parseCommaKeywords,
  sortCareerWatchAlerts,
  type CareerWatchAlert,
} from "@/lib/careerWatch";

type FetchMock = (input: unknown, init?: unknown) => Promise<Response>;

const originalFetch = globalThis.fetch;

function mockFetchOnce(response: Response) {
  (globalThis as { fetch: FetchMock }).fetch = async () => response;
}

describe("careerWatch keyword helpers", () => {
  it("mergeCommaKeywords adds remote without duplicates", () => {
    assert.equal(mergeCommaKeywords("python, remote", ["remote"]).value, "python, remote");
    assert.equal(mergeCommaKeywords("python", ["remote"]).value, "python, remote");
  });

  it("mergeCommaKeywords caps at CAREER_WATCH_MAX_KEYWORDS", () => {
    const many = Array.from({ length: CAREER_WATCH_MAX_KEYWORDS }, (_, i) => `kw${i}`);
    const merged = mergeCommaKeywords(many.join(", "), ["remote"]);
    assert.equal(merged.count, CAREER_WATCH_MAX_KEYWORDS);
    assert.equal(merged.truncated, true);
    assert.equal(parseCommaKeywords(merged.value).length, CAREER_WATCH_MAX_KEYWORDS);
  });
});

describe("sortCareerWatchAlerts", () => {
  const base = (id: string, score: number | null, created: string, notified?: string): CareerWatchAlert => ({
    id,
    status: "sent",
    match_score: score,
    match_reason: null,
    created_at: created,
    notified_at: notified ?? null,
    job_title: id,
    job_location: "",
    apply_url: "",
  });

  it("sorts by match score descending with latest tie-breaker", () => {
    const alerts = [
      base("a", 0.3, "2026-01-01T00:00:00Z"),
      base("b", 0.45, "2026-01-02T00:00:00Z"),
      base("c", 0.45, "2026-01-03T00:00:00Z"),
    ];
    const sorted = sortCareerWatchAlerts(alerts, "match");
    assert.deepEqual(sorted.map((a) => a.id), ["c", "b", "a"]);
  });

  it("sorts by notified/created time when mode is latest", () => {
    const alerts = [
      base("old", 0.9, "2026-01-01T00:00:00Z", "2026-01-01T12:00:00Z"),
      base("new", 0.2, "2026-01-05T00:00:00Z", "2026-01-05T12:00:00Z"),
    ];
    const sorted = sortCareerWatchAlerts(alerts, "latest");
    assert.deepEqual(sorted.map((a) => a.id), ["new", "old"]);
  });
});

describe("careerWatch apiFetch error handling", () => {
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("surfaces the backend's friendly detail.message on a structured error", async () => {
    mockFetchOnce(
      new Response(
        JSON.stringify({
          detail: {
            code: "career_watch_url_probe_failed",
            message: "Could not fetch job listings from this URL.",
            probe_status: "error",
            job_count: 0,
          },
        }),
        { status: 422 },
      ),
    );

    await assert.rejects(
      () => getCareerWatchLimits("token"),
      (err: Error) => {
        assert.equal(err.message, "Could not fetch job listings from this URL.");
        return true;
      },
    );
  });

  it("never leaks a raw JSON body or JSON.parse syntax error when the backend returns a non-JSON error (e.g. an upstream gateway failure)", async () => {
    mockFetchOnce(
      new Response("<html>502 Bad Gateway</html>", { status: 502 }),
    );

    await assert.rejects(
      () => getCareerWatchLimits("token"),
      (err: Error) => {
        assert.ok(!err.message.includes("<html>"));
        assert.ok(!/unexpected token/i.test(err.message));
        assert.equal(
          err.message,
          "Something went wrong. Please check the details and try again.",
        );
        return true;
      },
    );
  });

  it("maps FastAPI keyword too_long validation to a friendly message", async () => {
    mockFetchOnce(
      new Response(
        JSON.stringify({
          detail: [
            {
              type: "too_long",
              loc: ["body", "keywords"],
              msg: "List should have at most 20 items after validation, not 21",
            },
          ],
        }),
        { status: 422 },
      ),
    );

    await assert.rejects(
      () => getCareerWatchLimits("token"),
      (err: Error) => {
        assert.match(err.message, /at most 10 keywords/i);
        assert.ok(!err.message.includes("validation error"));
        return true;
      },
    );
  });

  it("falls back to a generic message when the error body has no detail.message", async () => {
    mockFetchOnce(new Response(JSON.stringify({ detail: {} }), { status: 500 }));

    await assert.rejects(
      () => getCareerWatchLimits("token"),
      (err: Error) => {
        assert.equal(
          err.message,
          "Something went wrong. Please check the details and try again.",
        );
        return true;
      },
    );
  });
});
