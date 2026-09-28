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
