/** Client-side check: do not send a backend JWT that NextAuth still holds after expiry. */
export function liveBackendAccessToken(session: {
  error?: string
  backendAccessToken?: string
  backendExpiresAt?: number
} | null | undefined): string | undefined {
  if (!session?.backendAccessToken) return undefined
  if (session.error === "TokenExpired") return undefined
  if (
    typeof session.backendExpiresAt === "number" &&
    Date.now() >= session.backendExpiresAt
  ) {
    return undefined
  }
  return session.backendAccessToken
}

/** True when NextAuth still has a backend JWT that the API will reject. */
export function needsBackendAccessRefresh(session: {
  error?: string
  backendAccessToken?: string
  backendExpiresAt?: number
} | null | undefined): boolean {
  return Boolean(session?.backendAccessToken) && !liveBackendAccessToken(session)
}

/** Sign-in URL after the refresh cookie cannot recover the session. */
export function expiredSessionAuthUrl(dest?: string): string {
  const path =
    dest ??
    (typeof window !== "undefined"
      ? `${window.location.pathname}${window.location.search}`
      : "/")
  return `/auth?callbackUrl=${encodeURIComponent(path)}`
}
