"use client"

/**
 * Client-side auth guards.
 */
import { signOut, useSession } from "next-auth/react"
import { useRouter } from "next/navigation"
import { useEffect, useRef, ComponentType } from "react"
import { fetchMe } from "@/lib/auth/api"
import { expiredSessionAuthUrl, needsBackendAccessRefresh } from "@/lib/auth/accessToken"
import { isOnboardingExempt, mustCompleteOnboarding, needsOnboarding } from "@/lib/auth/onboarding"
import {
  refreshBackendSession,
  isRefreshRateLimited,
  lastRefreshFailureHttpStatus,
} from "@/lib/auth/refreshBackendSession"
import { isStaleAuthError } from "@/lib/auth/staleSession"
import { saveAuthReturnUrl } from "@/lib/auth/returnUrl"

function currentPath(): string {
  if (typeof window === "undefined") return "/"
  return `${window.location.pathname}${window.location.search}`
}

/**
 * Redirects to /auth when the user is not signed in OR when their backend
 * token has expired. When onboarding is incomplete, redirects to /onboarding
 * except on exempt paths (profile, session wizard).
 */
export function useRequireAuth(callbackUrl?: string) {
  const { data: session, status, update } = useSession()
  const router = useRouter()
  const refreshingRef = useRef(false)
  const onboardingVerifyRef = useRef(false)
  const onboardingRedirectedRef = useRef(false)

  useEffect(() => {
    if (status === "loading") return

    const dest = callbackUrl ?? currentPath()
    const authUrl = `/auth?callbackUrl=${encodeURIComponent(dest)}`

    if (!session) {
      onboardingRedirectedRef.current = false
      saveAuthReturnUrl(dest)
      router.replace(authUrl)
      return
    }

    if (!session.backendAccessToken && session.error) {
      saveAuthReturnUrl(dest)
      router.replace(
        `/auth?error=${encodeURIComponent(session.error)}`,
      )
      return
    }

    if (needsBackendAccessRefresh(session)) {
      if (refreshingRef.current) return
      if (isRefreshRateLimited() && lastRefreshFailureHttpStatus() === 429) return
      if (isRefreshRateLimited()) {
        saveAuthReturnUrl(dest)
        void signOut({ callbackUrl: expiredSessionAuthUrl(dest) })
        return
      }
      refreshingRef.current = true
      void refreshBackendSession(update).then((ok) => {
        refreshingRef.current = false
        if (ok) return
        if (lastRefreshFailureHttpStatus() === 429) return
        saveAuthReturnUrl(dest)
        void signOut({ callbackUrl: expiredSessionAuthUrl(dest) })
      }).catch((err: unknown) => {
        refreshingRef.current = false
        const message = err instanceof Error ? err.message : ""
        if (isStaleAuthError(message) || lastRefreshFailureHttpStatus() === 401) {
          saveAuthReturnUrl(dest)
          void signOut({ callbackUrl: expiredSessionAuthUrl(dest) })
        }
      })
      return
    }

    const path = typeof window !== "undefined" ? window.location.pathname : dest
    if (path === "/onboarding") {
      onboardingRedirectedRef.current = false
    }

    const redirectToOnboarding = () => {
      if (!path || path === "/onboarding" || onboardingRedirectedRef.current) return
      onboardingRedirectedRef.current = true
      router.replace("/onboarding")
    }

    if (mustCompleteOnboarding(session) && path && !isOnboardingExempt(path)) {
      const accessToken = session.backendAccessToken
      if (accessToken && !onboardingVerifyRef.current) {
        onboardingVerifyRef.current = true
        void fetchMe(accessToken)
          .then(async (user) => {
            onboardingVerifyRef.current = false
            if (!needsOnboarding(user)) {
              onboardingRedirectedRef.current = false
              await update({ backendUser: user })
              return
            }
            redirectToOnboarding()
          })
          .catch(() => {
            onboardingVerifyRef.current = false
            redirectToOnboarding()
          })
        return
      }

      if (!onboardingVerifyRef.current) {
        redirectToOnboarding()
      }
    }
  }, [session, status, router, callbackUrl, update])

  return { session, status }
}

/**
 * Higher-order component that guards a client component behind auth.
 */
export function withAuth<P extends object>(
  Component: ComponentType<P>,
  callbackUrl?: string,
): ComponentType<P> {
  function AuthGuarded(props: P) {
    const { session, status } = useRequireAuth(callbackUrl)
    if (status === "loading" || !session) return null
    return <Component {...props} />
  }
  AuthGuarded.displayName = `withAuth(${Component.displayName ?? Component.name ?? "Component"})`
  return AuthGuarded
}
