/**
 * E2E: Career Watch — add a company (notifications) and remove it.
 */
import { test, expect, type Page, type Route } from "@playwright/test"
import { suppressTutorial } from "./helpers/guidance"

const API = "http://localhost:8000"

const MOCK_ACCESS = "mock-access-token-career-watch"
const WATCH_ID = "33333333-3333-3333-3333-333333333333"
const WATCHED_COMPANY_ID = "44444444-4444-4444-4444-444444444444"
const CAREERS_URL = "https://boards.greenhouse.io/acme"

const MOCK_USER = {
  id: "user-career-watch-e2e",
  email: "career-watch-e2e@example.com",
  display_name: "Career Watch E2E",
  tier: "paid",
  credit_balance: 0,
  auth_provider: "email",
  email_verified_at: "2026-05-01T00:00:00Z",
  onboarding_completed_at: "2026-05-01T00:00:00Z",
  onboarding_ai_choice: "platform",
  has_totp: false,
  closure_requested_at: null,
  suspended_at: null,
}

type MockWatch = {
  id: string
  watched_company_id: string
  company_name: string
  careers_page_url: string
  ats_type: string
  keywords: string[]
  is_active: boolean
  created_at: string
}

async function mockAuth(page: Page) {
  await suppressTutorial(page)
  await page.route(`${API}/api/auth/me`, (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_USER),
    }),
  )
  await page.route(`${API}/api/dashboard/summary`, (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        display_name: MOCK_USER.display_name,
        tier: MOCK_USER.tier,
        credit_balance: MOCK_USER.credit_balance,
        next_billing_date: null,
        subscription: null,
        counts: { resumes: 0, applications: 0, saved_jobs: 0 },
        recent_activity: [],
        ats_trend: [],
      }),
    }),
  )
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
  await page.route(`${API}/api/auth/refresh`, (route: Route) =>
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

async function mockSubscription(page: Page) {
  await page.route(`${API}/api/subscriptions/current`, (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        subscription: {
          id: "sub-career-watch-e2e",
          plan: "monthly",
          billing_cycle: "recurring",
          status: "active",
          trial_ends_at: null,
          period_start: "2026-05-01T00:00:00Z",
          period_end: "2026-06-01T00:00:00Z",
          resumes_used: 0,
          resumes_limit: 150,
          searches_used: 0,
          searches_limit: 300,
          cancel_at_period_end: false,
          paused_at: null,
          pause_resumes_at: null,
        },
        credit_balance: 0,
      }),
    }),
  )
}

async function mockCareerWatchApi(page: Page) {
  let watches: MockWatch[] = []

  await page.route(`${API}/api/career-watch/**`, async (route: Route) => {
    const url = new URL(route.request().url())
    const path = url.pathname
    const method = route.request().method()

    if (path === "/api/career-watch/limits" && method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          max_companies: 10,
          poll_interval_minutes: 30,
          active_watches: watches.length,
        }),
      })
    }

    if (path === "/api/career-watch/alerts" && method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      })
    }

    if (path === "/api/career-watch/detect" && method === "POST") {
      const body = route.request().postDataJSON() as { careers_page_url?: string }
      expect(body.careers_page_url).toBeTruthy()
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ats_type: "greenhouse",
          board_token: "acme",
          careers_page_url: body.careers_page_url,
          company_name: "Acme Corp",
        }),
      })
    }

    if (path === "/api/career-watch/watches" && method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(watches),
      })
    }

    if (path === "/api/career-watch/watches" && method === "POST") {
      const body = route.request().postDataJSON() as {
        careers_page_url: string
        company_name?: string
        keywords: string[]
      }
      expect(body.careers_page_url).toBe(CAREERS_URL)
      expect(body.keywords).toEqual(["python", "backend"])
      const entry: MockWatch = {
        id: WATCH_ID,
        watched_company_id: WATCHED_COMPANY_ID,
        company_name: body.company_name ?? "Acme Corp",
        careers_page_url: body.careers_page_url,
        ats_type: "greenhouse",
        keywords: body.keywords,
        is_active: true,
        created_at: "2026-05-28T12:00:00Z",
      }
      watches = [entry]
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(entry),
      })
    }

    const deleteMatch = path.match(/^\/api\/career-watch\/watches\/([^/]+)$/)
    if (deleteMatch && method === "DELETE") {
      const id = deleteMatch[1]
      watches = watches.filter((w) => w.id !== id)
      return route.fulfill({ status: 204, body: "" })
    }

    await route.continue()
  })
}

async function login(page: Page) {
  await page.goto("/auth")
  await page.getByPlaceholder("you@example.com").fill(MOCK_USER.email)
  await page.getByPlaceholder("••••••••••").fill("Str0ng!Password123")
  await page.locator("form").getByRole("button", { name: "Sign in" }).click()
  await page.waitForURL(/\/dashboard/, { timeout: 15_000 })
}

test("add company watch for notifications then remove", async ({ page }) => {
  await mockAuth(page)
  await mockSubscription(page)
  await mockCareerWatchApi(page)
  await login(page)

  await page.goto("/career-watch")
  await expect(page.getByRole("heading", { name: "Career Watch" })).toBeVisible()
  await expect(page.getByTestId("career-watch-empty")).toBeVisible()

  await page.locator("#cw-url").fill(CAREERS_URL)
  await page.getByRole("button", { name: "Detect ATS" }).click()
  await expect(page.getByTestId("career-watch-detected-ats")).toContainText("greenhouse", {
    timeout: 10_000,
  })

  await page.locator("#cw-name").fill("Acme Corp")
  await page.locator("#cw-keywords").fill("python, backend")
  await page.getByTestId("career-watch-add-submit").click()

  await expect(page.getByTestId("career-watch-list")).toBeVisible({ timeout: 10_000 })
  await expect(page.getByText("Acme Corp")).toBeVisible()
  const entry = page.getByTestId(`career-watch-entry-${WATCH_ID}`)
  await expect(entry.getByTestId(`career-watch-keywords-${WATCH_ID}`)).toContainText("python")
  await expect(entry.getByTestId(`career-watch-keywords-${WATCH_ID}`)).toContainText("backend")
  await expect(page.getByTestId("career-watch-limits-summary")).toHaveText(
    "1 / 10 companies watched",
  )

  await page.getByLabel("Remove watch").click()
  await expect(page.getByTestId("career-watch-empty")).toBeVisible({ timeout: 10_000 })
})
