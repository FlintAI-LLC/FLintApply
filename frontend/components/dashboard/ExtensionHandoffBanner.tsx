"use client"

import Link from "next/link"
import { ArrowRight, Plug } from "lucide-react"
import { useEffect, useState } from "react"
import { buildSessionNewUrl, getExtensionHandoff } from "@/lib/extensionHandoff"
import { PRODUCT_NAME } from "@/lib/brand"

/** Shown when the extension sent a JD but sign-in landed on the dashboard. */
export function ExtensionHandoffBanner() {
  const [tailorHref, setTailorHref] = useState<string | null>(null)

  useEffect(() => {
    const handoff = getExtensionHandoff()
    if (handoff) setTailorHref(buildSessionNewUrl(handoff))
  }, [])

  if (!tailorHref) return null

  return (
    <div
      className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
      data-testid="extension-handoff-banner"
      role="status"
    >
      <div className="flex gap-3 items-start">
        <Plug className="w-5 h-5 text-amber-700 dark:text-amber-400 shrink-0 mt-0.5" aria-hidden />
        <div>
          <p className="font-medium text-foreground">Job saved from the extension</p>
          <p className="text-sm text-muted-foreground mt-0.5">
            Continue in {PRODUCT_NAME} to tailor your resume for that posting — your job description
            is already loaded.
          </p>
        </div>
      </div>
      <Link
        href={tailorHref}
        className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-amber-700 hover:bg-amber-800 dark:bg-amber-600 dark:hover:bg-amber-500 text-white text-sm font-medium px-4 py-2 shrink-0"
      >
        Continue tailoring
        <ArrowRight className="w-4 h-4" aria-hidden />
      </Link>
    </div>
  )
}
