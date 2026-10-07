/**
 * E2E: extension → FlintApply tailoring handoff (jd_id, auth, error paths).
 *
 * Covers the acceptance criteria in docs/extension-tailor-handoff-brief.md
 * that require real page rendering (AC1, AC6, AC7, AC8, AC9, AC10, AC12).
 * AC2/AC3/AC4 (real OAuth provider round-trips) are not covered here — see
 * the brief deliverable for why.
 */
import { test, expect, type Page, type Route } from "@playwright/test"

// Relative navigation only — playwright.config.ts's `baseURL` already
// honours `PLAYWRIGHT_PORT` (host :3000 is reserved on this workstation).
// The backend origin is independent of the frontend port.
const API = "http://localhost:8000"

const MOCK_ACCESS = "mock-access-token-handoff-e2e"
const JD_ID = "33333333-3333-3333-3333-333333333333"

const MOCK_USER = {
  id: "user-handoff-e2e",
  email: "handoff-e2e@example.com",
  display_name: "Handoff E2E",
  tier: "free",
  credit_balance: 6,
  auth_provider: "email",
  email_verified_at: "2026-05-01T00:00:00Z",
  onboarding_completed_at: "2026-05-01T00:00:00Z",
  onboarding_ai_choice: "platform",
  has_totp: false,
  closure_requested_at: null,
  suspended_at: null,
}

const MOCK_JD = {
  id: JD_ID,
  url: "https://www.lenovo.com/careers/advanced-ai-enterprise-engineer",
  title: "Advanced AI Enterprise Engineer",
  company: "Lenovo",
  text: "We are hiring an Advanced AI Enterprise Engineer to build enterprise AI platforms.",
  source: "extension",
  created_at: "2026-05-01T00:00:00Z",
  session_id: null,
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
  await page.route(`${API}/api/auth/me`, (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_USER),
    }),
  )
}

async function mockDashboard(page: Page) {
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
  await page.route(`${API}/api/resumes*`, (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 10 }),
    }),
  )
  await page.route(`${API}/api/subscriptions/current`, (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ subscription: null, credit_balance: MOCK_USER.credit_balance }),
    }),
  )
}

/** Wizard bootstrap: new session + profile check, shared by every JD scenario. */
async function mockWizardBootstrap(page: Page) {
  await page.route(`${API}/api/sessions`, (route: Route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ session_id: "sess-handoff-e2e" }),
      })
    }
    return route.continue()
  })
  await page.route(`${API}/api/sessions/sess-handoff-e2e`, (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        session_id: "sess-handoff-e2e",
        ok: true,
        resume_raw: "",
        phases: {},
        stale: {},
        phase1_complete: false,
      }),
    }),
  )
  await page.route(`${API}/api/profile/resume`, (route: Route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ chunk_count: 0 }),
      })
    }
    return route.continue()
  })
}

async function login(page: Page) {
  await page.goto(`/auth`)
  await page.getByPlaceholder("you@example.com").fill(MOCK_USER.email)
  await page.getByPlaceholder("••••••••••").fill("Str0ng!Password123")
  await page.locator("form").getByRole("button", { name: "Sign in" }).click()
  await page.waitForURL(/\/dashboard/, { timeout: 15_000 })
}

test.describe("extension handoff — already signed in (AC1)", () => {
  test("jd_id in the URL fills JD text and prefills the application name field", async ({ page }) => {
    await mockAuth(page)
    await mockWizardBootstrap(page)
    await page.route(`${API}/api/job-descriptions/${JD_ID}`, (route: Route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_JD) }),
    )
    await login(page)

    await page.goto(`/session/new?jd_id=${JD_ID}&source=extension&step=jd`)
    await expect(page.getByRole("heading", { name: "Job description" })).toBeVisible({ timeout: 10_000 })
    await expect(page.getByTestId("application-name-field").locator("input")).toHaveValue(
      "Lenovo — Advanced AI Enterprise Engineer",
      { timeout: 10_000 },
    )
    await expect(
      page.getByPlaceholder("Paste the full job description here…"),
    ).toHaveValue(/Advanced AI Enterprise Engineer/, { timeout: 10_000 })
    await expect(page.getByTestId("jd-load-error")).toHaveCount(0)
  })
})

test.describe("extension handoff — JD fetch failures never render a silent blank form (I6)", () => {
  test("404 shows a specific message with a dashboard fallback, not a blank box (AC6)", async ({ page }) => {
    await mockAuth(page)
    await mockWizardBootstrap(page)
    await page.route(`${API}/api/job-descriptions/${JD_ID}`, (route: Route) =>
      route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Job not found" }) }),
    )
    await login(page)

    await page.goto(`/session/new?jd_id=${JD_ID}&source=extension&step=jd`)
    const banner = page.getByTestId("jd-load-error")
    await expect(banner).toBeVisible({ timeout: 10_000 })
    await expect(banner).toContainText(/different account|expired/i)
    await expect(banner.getByRole("link", { name: "Back to dashboard" })).toHaveAttribute("href", "/dashboard")
    // The textarea itself stays present and empty so the user can paste manually.
    await expect(page.getByPlaceholder("Paste the full job description here…")).toHaveValue("")
  })

  test("empty captured text shows a specific message, not a silent blank form (AC8)", async ({ page }) => {
    await mockAuth(page)
    await mockWizardBootstrap(page)
    await page.route(`${API}/api/job-descriptions/${JD_ID}`, (route: Route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...MOCK_JD, text: "" }),
      }),
    )
    await login(page)

    await page.goto(`/session/new?jd_id=${JD_ID}&source=extension&step=jd`)
    const banner = page.getByTestId("jd-load-error")
    await expect(banner).toBeVisible({ timeout: 10_000 })
    await expect(banner).toContainText(/captured this job but not its text/i)
    // "empty" is not retryable and does not offer a sign-in action.
    await expect(banner.getByRole("button", { name: "Try again" })).toHaveCount(0)
    await expect(banner.getByRole("button", { name: "Sign in again" })).toHaveCount(0)
  })

  test("401 offers sign-in-again and returns to the same jd_id after re-auth (AC7)", async ({ page }) => {
    await mockAuth(page)
    await mockWizardBootstrap(page)
    await page.route(`${API}/api/job-descriptions/${JD_ID}`, (route: Route) =>
      route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Access token expired" }) }),
    )
    await login(page)

    await page.goto(`/session/new?jd_id=${JD_ID}&source=extension&step=jd`)
    const banner = page.getByTestId("jd-load-error")
    await expect(banner).toBeVisible({ timeout: 10_000 })
    await expect(banner).toContainText(/session expired/i)

    await banner.getByRole("button", { name: "Sign in again" }).click()
    // Must land on the real login form, not bounce straight back to /dashboard
    // (proxy.ts's AUTH_ONLY_PATHS branch would do that for a live session).
    await page.waitForURL(/\/auth\?callbackUrl=/, { timeout: 10_000 })
    await expect(page.getByPlaceholder("you@example.com")).toBeVisible()

    await page.getByPlaceholder("you@example.com").fill(MOCK_USER.email)
    await page.getByPlaceholder("••••••••••").fill("Str0ng!Password123")
    await page.locator("form").getByRole("button", { name: "Sign in" }).click()

    // Back on the same job, not /dashboard.
    await page.waitForURL(/\/session\/new/, { timeout: 15_000 })
    expect(page.url()).toContain(`jd_id=${JD_ID}`)
  })
})

test.describe("extension handoff — consumption, expiry, and the dashboard banner", () => {
  test("a successfully loaded JD clears the handoff so the dashboard banner disappears, even after a step transition re-touches the URL (AC9)", async ({ page }) => {
    await mockAuth(page)
    await mockWizardBootstrap(page)
    await mockDashboard(page)
    await page.route(`${API}/api/job-descriptions/${JD_ID}`, (route: Route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_JD) }),
    )
    await login(page)

    await page.goto(`/session/new?jd_id=${JD_ID}&source=extension&step=jd`)
    await expect(
      page.getByPlaceholder("Paste the full job description here…"),
    ).toHaveValue(/Advanced AI Enterprise Engineer/, { timeout: 10_000 })

    // A bare "load, then check dashboard" assertion passes incidentally: it
    // never re-touches the URL after the JD loads, so it never exercises
    // captureExtensionHandoffFromParams re-running. goTo() re-adds jd_id to
    // the URL on every step transition (e.g. handleJD -> goTo("info")) —
    // "← Back" exercises the same goTo() path without needing to mock the
    // JD-submit backend calls. This is the step transition that must NOT
    // resurrect the just-consumed handoff.
    await page.getByRole("button", { name: /back/i }).click()
    await expect(page.getByRole("heading", { name: "Name this application" })).toBeVisible({
      timeout: 10_000,
    })

    await page.goto(`/dashboard`)
    // ExtensionHandoffBanner decides via a useEffect on mount — asserting
    // toHaveCount(0) immediately after goto() can pass vacuously before that
    // effect has committed, even when the handoff resurrected. Wait for a
    // signal that depends on DashboardView's own data fetch (which mounts
    // alongside the banner) before trusting an absence.
    await expect(page.getByText(/credits remaining/i)).toBeVisible({ timeout: 10_000 })
    await expect(page.getByTestId("extension-handoff-banner")).toHaveCount(0)
  })

  test("dashboard shows the banner for an unconsumed handoff and links to the wizard (AC12)", async ({ page }) => {
    await mockAuth(page)
    await mockDashboard(page)
    await login(page)

    await page.evaluate(
      ([jdId]) => {
        sessionStorage.setItem(
          "sr_extension_jd_handoff",
          JSON.stringify({ jd_id: jdId, source: "extension", step: "jd", captured_at: Date.now() }),
        )
      },
      [JD_ID],
    )
    await page.goto(`/dashboard`)

    const banner = page.getByTestId("extension-handoff-banner")
    await expect(banner).toBeVisible({ timeout: 10_000 })
    await expect(banner.getByRole("link", { name: /Continue tailoring/i })).toHaveAttribute(
      "href",
      `/session/new?step=jd&jd_id=${JD_ID}&source=extension`,
    )
  })

  test("a stale (TTL-expired) handoff does not show the dashboard banner (AC10)", async ({ page }) => {
    await mockAuth(page)
    await mockDashboard(page)
    await login(page)

    await page.evaluate(
      ([jdId]) => {
        sessionStorage.setItem(
          "sr_extension_jd_handoff",
          JSON.stringify({
            jd_id: jdId,
            source: "extension",
            step: "jd",
            captured_at: Date.now() - 31 * 60 * 1000, // TTL is 30 minutes
          }),
        )
      },
      [JD_ID],
    )
    await page.goto(`/dashboard`)

    await expect(page.getByTestId("extension-handoff-banner")).toHaveCount(0)
  })

  test("?fresh=1 ignores a stale extension handoff (defect #7)", async ({ page }) => {
    await mockAuth(page)
    await mockWizardBootstrap(page)
    let jdRequested = false
    await page.route(`${API}/api/job-descriptions/${JD_ID}`, (route: Route) => {
      jdRequested = true
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_JD) })
    })
    await login(page)

    await page.evaluate(
      ([jdId]) => {
        sessionStorage.setItem(
          "sr_extension_jd_handoff",
          JSON.stringify({ jd_id: jdId, source: "extension", step: "jd", captured_at: Date.now() }),
        )
      },
      [JD_ID],
    )
    await page.goto(`/session/new?fresh=1`)
    await expect(page.getByRole("heading", { name: "Name this application" })).toBeVisible({ timeout: 10_000 })
    expect(page.url()).not.toContain("jd_id")
    expect(jdRequested).toBe(false)
  })
})
