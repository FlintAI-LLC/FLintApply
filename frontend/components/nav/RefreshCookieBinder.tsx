"use client"

import { useEffect } from "react"
import { useSession } from "next-auth/react"
import { liveBackendAccessToken } from "@/lib/auth/accessToken"
import {
  bindRefreshCookie,
  resetBindRefreshCookie,
  shouldBindRefreshCookie,
} from "@/lib/auth/bindRefreshCookie"

/** Makes sure this browser holds the sr_refresh cookie after an SSO sign-in. */
export function RefreshCookieBinder() {
  const { data: session, status } = useSession()
  const token = liveBackendAccessToken(session)
  const userId = session?.backendUser?.id

  useEffect(() => {
    if (status === "unauthenticated") {
      resetBindRefreshCookie()
      return
    }
    if (!token || !userId || !shouldBindRefreshCookie({ status, token, userId })) return
    void bindRefreshCookie(userId, token)
  }, [status, token, userId])

  return null
}
