/** Admin Reports — how to read each tab (aligned with backend reporting). */

export type ReportGuideItem = {
  id: string
  label: string
  description: string
}

export const MONITORING_SUMMARY_GUIDE: {
  intro: string
  items: ReportGuideItem[]
} = {
  intro:
    "Top cards summarize the selected date range (From → To), except where noted as all-time.",
  items: [
    {
      id: "users_total",
      label: "Total users",
      description: "All accounts in the database (not limited to the date range).",
    },
    {
      id: "signups",
      label: "New signups",
      description: "Accounts created between From and To (inclusive, UTC).",
    },
    {
      id: "landing_views",
      label: "Landing views",
      description: "Sum of anonymous landing-page beacons in the range (same metric as the activity chart).",
    },
    {
      id: "signup_rate",
      label: "Signup rate",
      description: "New signups ÷ landing views in the range. Empty if there were no landing views.",
    },
    {
      id: "logged_in",
      label: "Logged-in users",
      description:
        "Distinct users with at least one successful login in the range; hint shows how many used web vs extension.",
    },
    {
      id: "product_opens",
      label: "Product opens",
      description:
        "Daily anonymous beacons: web app views plus extension opens (not the same as logins).",
    },
    {
      id: "active_subs",
      label: "Active subs",
      description: "Subscriptions in an active status right now (not limited to the date range).",
    },
    {
      id: "tracker",
      label: "Tracker",
      description:
        "All-time application tracker rows; hint shows all-time job search log count.",
    },
  ],
}

export const CHANNEL_METRICS_GUIDE: {
  intro: string
  items: ReportGuideItem[]
  footnote: string
} = {
  intro: "Each day in the range gets four counts. Logins are unique users; beacons are event totals.",
  items: [
    {
      id: "logins_web",
      label: "Web logins",
      description: "Distinct users who signed in via the web app that day (auth audit log).",
    },
    {
      id: "logins_extension",
      label: "Extension logins",
      description: "Distinct users who signed in via the Chrome extension that day.",
    },
    {
      id: "beacon_web_app",
      label: "Web opens (beacon)",
      description:
        "How many times the web app fired its once-per-day “app open” beacon (can exceed unique users).",
    },
    {
      id: "beacon_extension",
      label: "Extension opens",
      description: "Extension open beacons for that day (anonymous, aggregated).",
    },
  ],
  footnote: "Stacked bars group logins together and opens together; compare channels side by side per day.",
}

export const FUNNEL_GUIDE: {
  intro: string
  items: ReportGuideItem[]
  footnote: string
} = {
  intro:
    "Signup cohort for the selected date range only: every step counts users who registered in that window and reached the milestone (nested subsets, not independent audiences).",
  items: [
    {
      id: "registered",
      label: "Registered",
      description: "New accounts created in the range.",
    },
    {
      id: "email_verified",
      label: "Email verified",
      description: "Those signups with email_verified_at set.",
    },
    {
      id: "first_build",
      label: "First build",
      description: "Signups with at least one saved resume record.",
    },
    {
      id: "first_resume_build",
      label: "First resume build",
      description:
        "Signups with at least one resume_build credit transaction (Phase 3 full rewrite quota use).",
    },
    {
      id: "subscribed",
      label: "Subscribed",
      description: "Signups who currently have an active paid subscription.",
    },
  ],
  footnote:
    "Bar width is the raw count at each step — not a conversion percentage. Compare step sizes to see drop-off for this cohort.",
}

export const REVENUE_GUIDE: {
  intro: string
  items: ReportGuideItem[]
  footnote: string
} = {
  intro: "Snapshot of active catalog prices, not cash collected in the date range.",
  items: [
    {
      id: "plan",
      label: "Plan (horizontal axis / row)",
      description: "Plan code from active PlanConfig rows in the billing catalog.",
    },
    {
      id: "revenue_usd",
      label: "Revenue (USD) — bar height",
      description:
        "Configured list price for that plan (amount_cents ÷ 100). This is not Stripe-invoiced revenue for the selected dates.",
    },
    {
      id: "subscribers",
      label: "Subscribers — footer line",
      description:
        "Intended to show paying subscribers per plan; the API does not populate this yet, so you may see 0.",
    },
  ],
  footnote:
    "For real MRR and collections, use Stripe billing reports until webhook-based revenue is wired here.",
}

export const LLM_COST_GUIDE: {
  intro: string
  items: ReportGuideItem[]
  footnote: string
} = {
  intro:
    "When daily cost data is connected, each bar is one calendar day for the selected quality tier filter.",
  items: [
    {
      id: "cost_usd",
      label: "Cost",
      description: "Estimated provider spend for LLM calls that day (tier filter applies).",
    },
    {
      id: "revenue_usd",
      label: "Revenue",
      description: "Attributed subscription or usage revenue allocated to that tier/day.",
    },
    {
      id: "margin_usd",
      label: "Margin",
      description: "Revenue minus cost for that day (can be negative if cost exceeds attribution).",
    },
    {
      id: "tier_filter",
      label: "Tier filter (standard / better / best)",
      description: "Limits bars to resumes using that LLM quality tier.",
    },
  ],
  footnote:
    "Today the admin API only returns active LLM tier configuration; cost/revenue/margin bars stay empty until usage aggregation is implemented.",
}

export const CHURN_GUIDE: {
  intro: string
  items: ReportGuideItem[]
  footnote: string
} = {
  intro: "Subscription endings over a lookback window derived from your date range length.",
  items: [
    {
      id: "churn_rate",
      label: "Churn rate (chart)",
      description:
        "Currently maps to a count of subscriptions with ended_at in the lookback window — not yet a true rate by plan.",
    },
    {
      id: "plan",
      label: "By plan",
      description: "Per-plan churn series will appear when the backend exposes plan-level rates.",
    },
  ],
  footnote:
    "Changing From/To adjusts the churn API days parameter (span between dates). This tab is coarse until Stripe cancellation events are aggregated.",
}
