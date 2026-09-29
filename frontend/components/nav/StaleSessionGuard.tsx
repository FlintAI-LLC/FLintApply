"use client"

import { useEffect, useRef } from "react"
import { signOut, useSession } from "next-auth/react"
import { fetchMe } from "@/lib/auth/api"
import {
  expiredSessionAuthUrl,
  liveBackendAccessToken,
  needsBackendAccessRefresh,
} from "@/lib/auth/accessToken"
import { shouldSignOutForDeadSession } from "@/lib/auth/deadSession"
import {
  SESSION_DEAD_EVENT,
  isSessionDead,
  refreshUnrecoverable,
  requestBackendSessionRefresh,
  resetRefreshState,
} from "@/lib/auth/refreshBackendSession"
import { saveAuthReturnUrl } from "@/lib/auth/returnUrl"
import {
  SESSION_REVOKED_EVENT,
  sessionRevokedAuthUrl,
} from "@/lib/parseApiError"
import { isStaleAuthError } from "@/lib/auth/staleSession"

const DEAD_SESSION_CHECK_MS = 15_000

// Rotation can fix these; anything else from /me means the user row is gone.
const ROTATABLE_MESSAGES = new Set(["Access token expired", "Invalid access token"])

/**
 * The only component that signs the browser out for a dead session. Token
 * rotation belongs to BackendTokenRefresh; this guard reacts to its verdict
 * (refresh cookie rejected) and to server-side revocation.
 */
export function StaleSessionGuard() {
  const { data: session, status } = useSession()
  const sessionRef = useRef(session)
  const checkedTokenRef = useRef<string | null>(null)
  const serverRejectedRef = useRef(false)
  const signingOutRef = useRef(false)
  const unusableSinceRef = useRef<number | null>(null)

  const liveToken = liveBackendAccessToken(session)

  useEffect(() => {
    sessionRef.current = session
  }, [session])

  useEffect(() => {
    const onSessionRevoked = () => {
      if (signingOutRef.current) return
      signingOutRef.current = true
      void signOut({ callbackUrl: sessionRevokedAuthUrl() })
    }
    window.addEventListener(SESSION_REVOKED_EVENT, onSessionRevoked)
    return () => window.removeEventListener(SESSION_REVOKED_EVENT, onSessionRevoked)
  }, [])

  // Rotation cannot repair the session and the embedded token is unusable.
  useEffect(() => {
    if (status !== "authenticated") return

    const tearDownIfDead = () => {
      if (signingOutRef.current) return
      const unusable =
        needsBackendAccessRefresh(sessionRef.current) || serverRejectedRef.current
      const now = Date.now()
      if (!unusable) {
        unusableSinceRef.current = null
        return
      }
      unusableSinceRef.current ??= now

      const shouldSignOut = shouldSignOutForDeadSession({
        unusable,
        dead: isSessionDead(),
        exhausted: refreshUnrecoverable(),
        unusableForMs: now - unusableSinceRef.current,
      })
      if (!shouldSignOut) return

      signingOutRef.current = true
      const onAuthPage = window.location.pathname.startsWith("/auth")
      const dest = `${window.location.pathname}${window.location.search}`
      if (!onAuthPage) saveAuthReturnUrl(dest)
      void signOut({
        callbackUrl: onAuthPage ? "/auth" : expiredSessionAuthUrl(dest),
      })
    }

    tearDownIfDead()
    window.addEventListener(SESSION_DEAD_EVENT, tearDownIfDead)
    // A live token can outlast the refresh verdict, and the grace period needs
    // a clock; re-check as time passes.
    const id = window.setInterval(tearDownIfDead, DEAD_SESSION_CHECK_MS)
    return () => {
      window.removeEventListener(SESSION_DEAD_EVENT, tearDownIfDead)
      window.clearInterval(id)
    }
  }, [status])

  useEffect(() => {
    if (status === "unauthenticated") {
      checkedTokenRef.current = null
      serverRejectedRef.current = false
      signingOutRef.current = false
      unusableSinceRef.current = null
      // Verdicts belong to the user who just left; the next sign-in starts clean.
      resetRefreshState()
      return
    }
    if (status !== "authenticated") return

    // Expired tokens are BackendTokenRefresh's job — never send them to /me.
    if (!liveToken || checkedTokenRef.current === liveToken) return

    void (async () => {
      checkedTokenRef.current = liveToken
      serverRejectedRef.current = false
      try {
        await fetchMe(liveToken)
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : ""
        if (!isStaleAuthError(message)) return
        if (signingOutRef.current) return

        if (ROTATABLE_MESSAGES.has(message)) {
          serverRejectedRef.current = true
          requestBackendSessionRefresh()
          return
        }

        signingOutRef.current = true
        void signOut({ callbackUrl: sessionRevokedAuthUrl() })
      }
    })()
  }, [status, liveToken])

  return null
}
