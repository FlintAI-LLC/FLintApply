import { describe, it, afterEach } from "node:test";
import assert from "node:assert/strict";

import { getCareerWatchLimits } from "@/lib/careerWatch";

type FetchMock = (input: unknown, init?: unknown) => Promise<Response>;

const originalFetch = globalThis.fetch;

function mockFetchOnce(response: Response) {
  (globalThis as { fetch: FetchMock }).fetch = async () => response;
}

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
