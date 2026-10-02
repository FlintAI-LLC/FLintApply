/**
 * E2E: Draft review panel on rewrite step (mocked session + draft-review API).
 */
import { test, expect, type Page, type Route } from "@playwright/test"

const BASE = "http://localhost:3000"
const API = "http://localhost:8000"

const SESSION_ID = "e2e-draft-review-session"
const MOCK_ACCESS = "mock-access-token-draft-review"

const MOCK_USER = {
  id: "user-draft-review-e2e",
  email: "draft-review-e2e@example.com",
  display_name: "Draft Review E2E",
  tier: "free",
  credit_balance: 6,
  auth_provider: "email",
  email_verified_at: "2026-05-01T00:00:00Z",
  has_totp: false,
  closure_requested_at: null,
  suspended_at: null,
}

const tailoredOutput = {
  contact: { name: "Jane Doe" },
  summary: "Tailored summary with Python keywords.",
  skills: ["Python"],
  experience: [
    {
      title: "Engineer",
      company: "Acme",
      dates: "2020–2024",
      bullets: ["Built APIs in Python", "Led platform migration"],
      removed_bullets: [],
      keywords_injected: [],
    },
  ],
  projects: [],
  education: [],
  certifications: [],
  rewrite_notes: [],
  metrics_needed: [],
}

const draftReviewPayload = {
  bullets: [
    {
      id: "experience:0:0",
      section: "experience",
      text: "Built APIs in Python",
      source_brick_ids: [],
      rewrite_notes: "",
      lint_issues: [],
    },
    {
      id: "experience:0:1",
      section: "experience",
      text: "Led platform migration",
      source_brick_ids: [],
      rewrite_notes: "",
      lint_issues: [],
    },
  ],
  skills: ["Python"],
  duplicate_candidates: [],
  keyword_coverage: {
    must_have: ["Python"],
    covered: ["Python"],
    missing: [],
  },
  length_estimate: { pages: 0.4, within_target: true },
}

function sessionPayload() {
  return {
    session_id: SESSION_ID,
    ok: true,
    resume_raw: "Jane Doe resume",
    phase1_complete: true,
    stale: { "3": null, "4": null },
    phases: {
      "1": {
        status: "done",
        output: {
          must_have_keywords: [
            {
              term: "Python",
              source_sentence: "",
              category: "skill",
              tier: "must_have",
              reason: "",
              present_in_resume: true,
            },
          ],
          nice_to_have_keywords: [],
          action_verbs: [],
          seniority_signals: [],
          boolean_search_terms: [],
          role_context: {
            career_level: "mid",
            needs_ml_framing: false,
            primary_domain: "software",
          },
        },
      },
      "2": {
        status: "done",
        output: {
          keyword_coverage: { present: ["Python"], missing_must_have: [], missing_nice_to_have: [] },
          bullet_issues: [],
          cliches_found: [],
          irrelevant_sections: [],
          page_estimate: "1 page",
          page_limit_exceeded: false,
          contact_issues: [],
          overall_score: 72,
          summary: "Audit ok.",
        },
      },
      "3": { status: "done", output: tailoredOutput },
      "4": { status: "pending", output: null },
    },
  }
}

async function mockAuth(page: Page) {
  await page.route(`${API}/api/auth/login`, (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        access_token: MOCK_ACCESS,
        token_type: "bearer",
        expires_in: 900,
        user: MOCK_USER,
      }),
    }),
  )
}

async function login(page: Page) {
  await page.goto(`${BASE}/auth`)
  await page.getByPlaceholder("you@example.com").fill(MOCK_USER.email)
  await page.getByPlaceholder("••••••••••").fill("Str0ng!Password123")
  await page.locator("form").getByRole("button", { name: "Sign in" }).click()
  await page.waitForURL(/\/dashboard/, { timeout: 15_000 })
}

async function mockSessionAndDraftReview(page: Page) {
  let review = { ...draftReviewPayload, bullets: [...draftReviewPayload.bullets] }

  await page.route(`${API}/api/sessions/${SESSION_ID}`, async (route: Route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(sessionPayload()),
      })
      return
    }
    await route.continue()
  })

  await page.route(`${API}/api/sessions/${SESSION_ID}/draft-review`, async (route: Route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(review),
      })
      return
    }
    await route.continue()
  })

  await page.route(
    `${API}/api/sessions/${SESSION_ID}/draft/bullets/experience:0:0`,
    async (route: Route) => {
      if (route.request().method() === "DELETE") {
        review = {
          ...review,
          bullets: review.bullets.filter((b) => b.id !== "experience:0:0"),
        }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(review),
        })
        return
      }
      await route.continue()
    },
  )
}

test("rewrite step shows draft review and delete updates panel", async ({ page }) => {
  await mockAuth(page)
  await mockSessionAndDraftReview(page)
  await login(page)

  await page.goto(`${BASE}/session/${SESSION_ID}?step=rewrite`)
  const panel = page.getByTestId("draft-review-panel")
  await expect(panel).toBeVisible({ timeout: 15_000 })
  await expect(panel.getByRole("heading", { name: "Draft review" })).toBeVisible()
  await expect(panel.getByText("Built APIs in Python")).toBeVisible()

  await panel.getByRole("button", { name: "Remove from draft (keeps master bricks)" }).first().click()
  await expect(panel.getByText("Built APIs in Python")).toBeHidden({ timeout: 10_000 })
  await expect(panel.getByText("Led platform migration")).toBeVisible()
})

test("rewrite step shows empty state when draft-review 404", async ({ page }) => {
  await mockAuth(page)
  await page.route(`${API}/api/sessions/${SESSION_ID}`, async (route: Route) => {
    if (route.request().method() === "GET") {
      const body = sessionPayload()
      body.phases["3"] = { status: "pending", output: null }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(body),
      })
      return
    }
    await route.continue()
  })
  await page.route(`${API}/api/sessions/${SESSION_ID}/draft-review`, (route: Route) =>
    route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ detail: "No draft resume for session" }),
    }),
  )
  await login(page)

  await page.goto(`${BASE}/session/${SESSION_ID}?step=rewrite`)
  await expect(page.getByTestId("draft-review-empty")).toBeVisible({ timeout: 15_000 })
})
