"use client"

import { DashboardView } from "@/components/dashboard/DashboardView"
import { useRequireAuth } from "@/lib/auth/guards"
import { useLiveBackendAccessToken } from "@/hooks/useLiveBackendAccessToken"
import { Loader2 } from "lucide-react"

export default function DashboardPage() {
  useRequireAuth("/dashboard")
  const { token, authLoading, status } = useLiveBackendAccessToken()

  if (status === "loading" || authLoading || !token) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-amber-700 dark:text-amber-400" />
      </div>
    )
  }

  return <DashboardView token={token} />
}
