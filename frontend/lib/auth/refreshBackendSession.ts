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

const REFRESH_429_BLOCK_MS = 60_000
const REFRESH_401_BLOCK_MS = 5 * 60_000

/** True while refresh is in cooldown after a 429 or hard 401. */
export function isRefreshRateLimited(): boolean {
  return Date.now() < refreshBlockedUntil
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
      await update({
        backendAccessToken: data.access_token,
        backendExpiresAt: Date.now() + data.expires_in * 1000,
        backendUser: data.user,
      })
      return true
    } catch (err) {
      if (err instanceof RefreshHttpError) {
        lastRefreshFailureStatus = err.status
      }
      if (err instanceof RefreshHttpError && err.status === 429) {
        refreshBlockedUntil = Date.now() + REFRESH_429_BLOCK_MS
      }
      if (err instanceof RefreshHttpError && err.status === 401) {
        refreshBlockedUntil = Date.now() + REFRESH_401_BLOCK_MS
        // Callers decide whether to sign out. useRequireAuth signs out on 401
        // so pages never sit on "Access token expired".
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
