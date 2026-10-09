import type { ActivityMetrics, FunnelMetrics } from "./types"

/** Build funnel data array for recharts FunnelChart. */
export function buildFunnelData(metrics: FunnelMetrics) {
  return [
    { name: "Registered", value: metrics.registered },
    { name: "Email verified", value: metrics.email_verified },
    { name: "First build", value: metrics.first_build },
    { name: "First export", value: metrics.first_export },
    { name: "Subscribed", value: metrics.subscribed },
  ]
}

/** Return default date range: last 30 days. */
export function defaultDateRange(): { from: string; to: string } {
  const today = new Date().toISOString().slice(0, 10)
  const thirtyDaysAgo = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10)
  return { from: thirtyDaysAgo, to: today }
}

export function signupConversionPct(summary: {
  landing_views: number
  signups_in_range: number
}): number | null {
  if (summary.landing_views <= 0) return null
  return (summary.signups_in_range / summary.landing_views) * 100
}

export function hasActivityData(metrics: ActivityMetrics[]): boolean {
  return metrics.some(
    (m) =>
      m.dau > 0 ||
      m.new_registrations > 0 ||
      m.landing_views > 0 ||
      m.dau_web > 0 ||
      m.dau_extension > 0,
  )
}
