"use client"

import Link from "next/link"
import { useEffect, useRef } from "react"
import { useSession } from "next-auth/react"
import { MailWarning } from "lucide-react"
import { fetchMe } from "@/lib/auth/api"
import { liveBackendAccessToken } from "@/lib/auth/accessToken"
import { needsEmailVerification } from "@/lib/auth/emailVerification"

/** Sticky strip under the nav when a password account has not verified email yet. */
export function EmailVerificationBanner() {
  const { data: session, status, update } = useSession()
  const syncedRef = useRef(false)
  const token = liveBackendAccessToken(session)

  useEffect(() => {
    if (status !== "authenticated" || !token || syncedRef.current) return
    syncedRef.current = true
    void fetchMe(token)
      .then((user) => update({ backendUser: user }))
      .catch(() => {
        syncedRef.current = false
      })
  }, [status, token, update])

  if (status !== "authenticated" || !session?.backendAccessToken) return null
  if (!needsEmailVerification(session.backendUser)) return null

  return (
    <div className="border-b border-amber-500/30 bg-amber-50 dark:bg-amber-950/40">
      <div className="max-w-6xl mx-auto px-4 py-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-amber-950 dark:text-amber-100">
        <MailWarning className="w-4 h-4 shrink-0 text-amber-700 dark:text-amber-400" />
        <span>
          Your email is not verified yet. Some credits stay locked until you confirm your inbox.
        </span>
        <Link
          href="/settings#email-verification"
          className="font-semibold text-amber-900 dark:text-amber-200 underline underline-offset-2 hover:text-amber-950 dark:hover:text-white"
        >
          Open Settings to resend the link
        </Link>
      </div>
    </div>
  )
}
