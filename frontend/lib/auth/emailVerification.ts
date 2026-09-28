import type { BackendUser } from "@/auth"

/** Password signups must confirm inbox; OAuth providers are trusted on the server. */
export function needsEmailVerification(user?: BackendUser | null): boolean {
  if (!user?.email) return false
  if (user.email_verified_at) return false
  return user.auth_provider === "email"
}
