export type AuthStatus = "loading" | "authenticated" | "unauthenticated"

/**
 * Header identity follows the NextAuth session, not the embedded API token,
 * which is cleared and restored during rotation and must not flip the menu.
 * The session is accepted (and only checked for presence) so callers cannot
 * accidentally couple the menu to its token fields.
 */
export function shouldShowUserMenu(
  status: AuthStatus,
  session: object | null | undefined,
  sessionDead: boolean,
): boolean {
  return status === "authenticated" && session != null && !sessionDead
}
