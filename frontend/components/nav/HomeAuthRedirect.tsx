"use client"

import { useEffect } from "react"
import { usePathname, useRouter } from "next/navigation"
import { useSession } from "next-auth/react"
import { liveBackendAccessToken } from "@/lib/auth/accessToken"
import { postAuthLandingPath } from "@/lib/auth/onboarding"

/** Server proxy redirects `/` when JWT has a backend token; this covers client nav races. */
export function HomeAuthRedirect() {
  const pathname = usePathname()
  const router = useRouter()
  const { data: session, status } = useSession()

  useEffect(() => {
    if (pathname !== "/" || status !== "authenticated") return
    if (!liveBackendAccessToken(session)) return
    router.replace(postAuthLandingPath(session))
  }, [pathname, status, session, router])

  return null
}
