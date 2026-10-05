"use client"

/**
 * Client-side auth guards.
 */
import { useSession } from "next-auth/react"
import { useRouter } from "next/navigation"
import { useEffect, useRef, ComponentType } from "react"
import { fetchMe } from "@/lib/auth/api"
import { liveBackendAccessToken, needsBackendAccessRefresh } from "@/lib/auth/accessToken"
import { isOnboardingExempt, mustCompleteOnboarding, needsOnboarding } from "@/lib/auth/onboarding"
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

    // BackendTokenRefresh owns rotation and StaleSessionGuard owns sign-out;
    // wait here rather than racing either of them.
    if (needsBackendAccessRefresh(session)) return

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
      const accessToken = liveBackendAccessToken(session)
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
