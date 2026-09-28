import assert from "node:assert/strict"
import test from "node:test"
import { needsEmailVerification } from "@/lib/auth/emailVerification"
import type { BackendUser } from "@/auth"

const base: BackendUser = {
  id: "u1",
  email: "a@example.com",
  display_name: "A",
  tier: "free",
  credit_balance: 6,
  spendable_credit_balance: 0,
  credits_locked_until_verification: true,
  auth_provider: "email",
  email_verified_at: null,
  has_totp: false,
  closure_requested_at: null,
  suspended_at: null,
  onboarding_completed_at: null,
  onboarding_ai_choice: null,
}

test("needsEmailVerification for unverified password signup", () => {
  assert.equal(needsEmailVerification(base), true)
})

test("needsEmailVerification false when verified", () => {
  assert.equal(
    needsEmailVerification({ ...base, email_verified_at: "2026-01-01T00:00:00Z" }),
    false,
  )
})

test("needsEmailVerification false for OAuth before server trust sync", () => {
  assert.equal(
    needsEmailVerification({ ...base, auth_provider: "microsoft" }),
    false,
  )
})
