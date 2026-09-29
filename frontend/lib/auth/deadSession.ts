/** How long an unusable token may sit in the UI after refresh gave up (5xx / network). */
export const UNRECOVERABLE_GRACE_MS = 60_000

export interface DeadSessionInput {
  /** The embedded API token cannot be used (expired, or the server rejected it). */
  unusable: boolean
  /** The refresh cookie was rejected with 401. */
  dead: boolean
  /** Refresh used its retry budget on non-429 failures. */
  exhausted: boolean
  /** How long the token has been continuously unusable. */
  unusableForMs: number
}

/**
 * Sign-out decision for a session that rotation cannot repair. A rejected
 * cookie is final; exhausted retries get a grace period so a brief outage does
 * not bounce the user, but a broken page can never stay up indefinitely.
 */
export function shouldSignOutForDeadSession(input: DeadSessionInput): boolean {
  if (!input.unusable) return false
  if (input.dead) return true
  return input.exhausted && input.unusableForMs >= UNRECOVERABLE_GRACE_MS
}
