import { isStaleAuthError } from "@/lib/auth/staleSession"

export interface PostAuthHandlers<TUser> {
  onUser: (user: TUser) => void
  onStale: () => void
}

/**
 * Runs the post-sign-in /me check at most once per access token so a stale
 * token can never drive an unbounded fetch/sign-out cycle.
 */
export class PostAuthAttemptGuard<TUser> {
  private attemptedToken: string | null = null
  private redirected = false

  reset(): void {
    this.attemptedToken = null
    this.redirected = false
  }

  async verify(
    token: string,
    fetchUser: (token: string) => Promise<TUser>,
    handlers: PostAuthHandlers<TUser>,
  ): Promise<void> {
    if (this.redirected || this.attemptedToken === token) return
    this.attemptedToken = token

    try {
      const user = await fetchUser(token)
      if (this.redirected) return
      this.redirected = true
      handlers.onUser(user)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : ""
      if (isStaleAuthError(message)) handlers.onStale()
    }
  }
}
