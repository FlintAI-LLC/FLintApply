import { needsBackendAccessRefresh } from "@/lib/auth/accessToken"

export type AuthStatus = "loading" | "authenticated" | "unauthenticated"

type NavSession = {
  backendAccessToken?: string
  backendExpiresAt?: number
  backendUser?: unknown
  error?: string
} | null | undefined

/**
 * App chrome (Dashboard / credits / user menu) requires a FlintApply backend
 * session — not a bare OAuth NextAuth shell. That prevents marketing `/` from
 * showing the logged-in nav after sign-out while Google profile data lingers.
 * During token rotation, ``backendUser`` (and TokenExpired) keep the menu up
 * while ``backendAccessToken`` is briefly cleared.
 */
export function shouldShowUserMenu(
  status: AuthStatus,
  session: NavSession,
  sessionDead: boolean,
): boolean {
  if (status !== "authenticated" || session == null || sessionDead) return false
  if (session.backendUser != null) return true
  if (session.backendAccessToken) return true
  if (session.error === "TokenExpired") return true
  if (needsBackendAccessRefresh(session)) return true
  return false
}
