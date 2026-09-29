import type { Session } from "next-auth"
import { invalidateSubscriptionCache } from "@/lib/api"
import type { BackendUser } from "@/auth"

type SessionUpdate = (data?: {
  backendAccessToken?: string
  backendExpiresAt?: number
  backendUser?: BackendUser
}) => Promise<Session | null>

let inflightRefresh: Promise<boolean> | null = null
let refreshBlockedUntil = 0
let lastRefreshFailureStatus: number | null = null
let consecutiveFailures = 0
let sessionDead = false
let refreshExhausted = false
let lastRequestAt = 0

export const REFRESH_429_BLOCK_MS = 60_000
export const REFRESH_401_BLOCK_MS = 5 * 60_000
export const MAX_CONSECUTIVE_FAILURES = 3
export const REFRESH_REQUEST_MIN_INTERVAL_MS = 5_000

/** Fired on window when the refresh cookie is rejected (401). */
export const SESSION_DEAD_EVENT = "sr:session-dead"

/**
 * Ask the single refresh owner (BackendTokenRefresh) to rotate the token.
 * Other components must use this instead of calling refreshBackendSession.
 */
export const BACKEND_REFRESH_REQUEST_EVENT = "sr:backend-refresh-request"

export function requestBackendSessionRefresh(): void {
  if (typeof window === "undefined") return
  const now = Date.now()
  if (now - lastRequestAt < REFRESH_REQUEST_MIN_INTERVAL_MS) return
  lastRequestAt = now
  window.dispatchEvent(new Event(BACKEND_REFRESH_REQUEST_EVENT))
}

/** True while refresh is in cooldown after a 429, hard 401, or repeated failures. */
export function isRefreshRateLimited(): boolean {
  return Date.now() < refreshBlockedUntil
}

/** True once the server rejected the refresh cookie; cleared by a successful refresh. */
export function isSessionDead(): boolean {
  return sessionDead
}

/**
 * True when rotation cannot recover this session: the cookie was rejected, or
 * repeated non-429 failures used up the retry budget.
 */
export function refreshUnrecoverable(): boolean {
  return sessionDead || refreshExhausted
}

/** Forget all refresh verdicts. Called on sign-out so the next user starts clean. */
export function resetRefreshState(): void {
  refreshBlockedUntil = 0
  lastRefreshFailureStatus = null
  consecutiveFailures = 0
  sessionDead = false
  refreshExhausted = false
  lastRequestAt = 0
}

/** HTTP status of the last failed refresh, if any. */
export function lastRefreshFailureHttpStatus(): number | null {
  return lastRefreshFailureStatus
}

class RefreshHttpError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = "RefreshHttpError"
  }
}

async function fetchRefresh(): Promise<{
  access_token: string
  expires_in: number
  user: BackendUser
}> {
  const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
  const res = await fetch(`${BASE}/api/auth/refresh`, {
    method: "POST",
    credentials: "include",
  })
  if (!res.ok) {
    let message = `HTTP ${res.status}`
    try {
      const body = await res.json()
      message = body?.detail?.code ?? body?.detail ?? message
    } catch {
      // ignore
    }
    throw new RefreshHttpError(String(message), res.status)
  }
  return res.json()
}

/** Rotate the backend access token via the httpOnly refresh cookie (single-flight). */
export async function refreshBackendSession(update: SessionUpdate): Promise<boolean> {
  if (isRefreshRateLimited()) return false
  if (inflightRefresh) return inflightRefresh

  inflightRefresh = (async () => {
    try {
      const data = await fetchRefresh()
      invalidateSubscriptionCache()
      lastRefreshFailureStatus = null
      consecutiveFailures = 0
      sessionDead = false
      refreshExhausted = false
      await update({
        backendAccessToken: data.access_token,
        backendExpiresAt: Date.now() + data.expires_in * 1000,
        backendUser: data.user,
      })
      return true
    } catch (err) {
      const status = err instanceof RefreshHttpError ? err.status : null
      lastRefreshFailureStatus = status
      consecutiveFailures += 1

      if (status === 429) {
        refreshBlockedUntil = Date.now() + REFRESH_429_BLOCK_MS
      }
      if (status === 401) {
        refreshBlockedUntil = Date.now() + REFRESH_401_BLOCK_MS
        sessionDead = true
        consecutiveFailures = 0
        // StaleSessionGuard is the only place that signs the user out.
        if (typeof window !== "undefined") {
          window.dispatchEvent(new Event(SESSION_DEAD_EVENT))
        }
      } else if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
        // Network errors and 5xx must not turn into an unbounded retry loop.
        // A fresh budget per window keeps the cooldown from re-tripping on one attempt.
        refreshBlockedUntil = Math.max(
          refreshBlockedUntil,
          Date.now() + REFRESH_401_BLOCK_MS,
        )
        consecutiveFailures = 0
        // Rate limiting is the server saying "wait", not "this session is gone".
        if (status !== 429) refreshExhausted = true
      }
      return false
    } finally {
      inflightRefresh = null
    }
  })()

  return inflightRefresh
}

/** Refresh if the access token expires within `bufferMs` (default 1 h). */
export async function refreshBackendSessionIfNeeded(
  update: SessionUpdate,
  expiresAt: number | undefined,
  bufferMs = 60 * 60 * 1000,
): Promise<boolean> {
  if (!expiresAt || Date.now() < expiresAt - bufferMs) return false
  return refreshBackendSession(update)
}
