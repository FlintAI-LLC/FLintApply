export const MAX_BIND_ATTEMPTS = 2

let boundUserId: string | null = null
const failedAttempts = new Map<string, number>()
let inflight: Promise<boolean> | null = null
let inflightUserId: string | null = null

export interface BindGateInput {
  status: "loading" | "authenticated" | "unauthenticated"
  /** Live (unexpired) backend access token, if any. */
  token: string | undefined
  userId: string | undefined
}

/** Whether the signed-in browser should ask for its sr_refresh cookie now. */
export function shouldBindRefreshCookie(input: BindGateInput): boolean {
  return (
    input.status === "authenticated" &&
    Boolean(input.token?.trim()) &&
    Boolean(input.userId)
  )
}

/**
 * Ask the API to set the httpOnly sr_refresh cookie in this browser.
 *
 * OAuth sign-in exchanges tokens from the Next.js server, so the cookie that
 * call sets never reaches the browser. Idempotent per tab and user: one success
 * ends it, and failures (including 409 "already spent") are capped per user so
 * a broken endpoint cannot become a retry loop.
 */
export async function bindRefreshCookie(
  userId: string,
  accessToken: string,
): Promise<boolean> {
  if (!accessToken.trim()) return false
  if (boundUserId === userId) return true
  if (inflight && inflightUserId === userId) return inflight
  if ((failedAttempts.get(userId) ?? 0) >= MAX_BIND_ATTEMPTS) return false

  const recordFailure = () =>
    failedAttempts.set(userId, (failedAttempts.get(userId) ?? 0) + 1)

  inflightUserId = userId
  inflight = (async () => {
    try {
      const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
      const res = await fetch(`${base}/api/auth/refresh-cookie`, {
        method: "POST",
        credentials: "include",
        headers: { Authorization: `Bearer ${accessToken}` },
      })
      if (!res.ok) {
        recordFailure()
        return false
      }
      boundUserId = userId
      failedAttempts.delete(userId)
      return true
    } catch {
      recordFailure()
      return false
    } finally {
      inflight = null
      inflightUserId = null
    }
  })()

  return inflight
}

/** Forget per-tab state so a later sign-in in this tab binds again. */
export function resetBindRefreshCookie(): void {
  boundUserId = null
  failedAttempts.clear()
  inflight = null
  inflightUserId = null
}
