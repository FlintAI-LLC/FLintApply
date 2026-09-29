"use client"

import { useEffect, useRef } from "react"
import { getSession, useSession } from "next-auth/react"
import { liveBackendAccessToken } from "@/lib/auth/accessToken"
import {
  BACKEND_REFRESH_REQUEST_EVENT,
  refreshBackendSession,
  refreshBackendSessionIfNeeded,
} from "@/lib/auth/refreshBackendSession"

// Access tokens last 15 minutes. Poll often enough to rotate before expiry.
const POLL_MS = 60 * 1000
const REFRESH_BUFFER_MS = 2 * 60 * 1000

/**
 * Sole owner of backend token rotation. Every other component asks for a
 * refresh through requestBackendSessionRefresh() so callers cannot race.
 */
export function BackendTokenRefresh() {
  const { data: session, status, update } = useSession()
  const updateRef = useRef(update)
  const sessionRef = useRef(session)
  useEffect(() => {
    updateRef.current = update
    sessionRef.current = session
  }, [update, session])

  const expiredRecoveryRef = useRef(false)

  // One-shot recovery when the JWT is already dead on the client (or NextAuth
  // has marked TokenExpired) — do not wait for the poll interval. Deps are the
  // specific fields read so update() cannot re-arm the effect.
  useEffect(() => {
    const current = sessionRef.current
    if (status !== "authenticated" || !current?.backendAccessToken) {
      expiredRecoveryRef.current = false
      return
    }
    if (liveBackendAccessToken(current)) {
      expiredRecoveryRef.current = false
      return
    }
    if (expiredRecoveryRef.current) return
    expiredRecoveryRef.current = true
    void refreshBackendSession(updateRef.current)
  }, [status, session?.error, session?.backendExpiresAt])

  // Refresh requests from other components (e.g. credit balance changed).
  useEffect(() => {
    const onRequest = () => {
      void refreshBackendSession(updateRef.current)
    }
    window.addEventListener(BACKEND_REFRESH_REQUEST_EVENT, onRequest)
    return () =>
      window.removeEventListener(BACKEND_REFRESH_REQUEST_EVENT, onRequest)
  }, [])

  // Periodic proactive refresh — deps stable so session.update() does not re-arm loops.
  useEffect(() => {
    if (status !== "authenticated") return

    const tick = async () => {
      const current = await getSession()
      const expiresAt = (current as { backendExpiresAt?: number } | null)
        ?.backendExpiresAt
      await refreshBackendSessionIfNeeded(
        updateRef.current,
        expiresAt,
        REFRESH_BUFFER_MS,
      )
    }

    void tick()
    const id = window.setInterval(() => {
      void tick()
    }, POLL_MS)

    return () => window.clearInterval(id)
  }, [status])

  return null
}
