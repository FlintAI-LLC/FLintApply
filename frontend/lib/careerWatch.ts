const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export type CareerWatchLimits = {
  max_companies: number
  poll_interval_minutes: number
  active_watches: number
}

export type CareerWatchEntry = {
  id: string
  watched_company_id: string
  company_name: string
  careers_page_url: string
  ats_type: string
  keywords: string[]
  is_active: boolean
  created_at: string
}

export type CareerWatchAlert = {
  id: string
  status: string
  match_score: number | null
  match_reason: string | null
  created_at: string
  notified_at: string | null
  job_title: string
  job_location: string
  apply_url: string
}

export type DetectResult = {
  ats_type: string
  board_token: string | null
  careers_page_url: string
  company_name: string | null
  probe_status: "ok" | "warning" | "error"
  job_count: number
  probe_message: string
}

export type CareerAlertSort = "latest" | "match"

/** Must match backend `CreateWatchRequest.keywords` max_length. */
export const CAREER_WATCH_MAX_KEYWORDS = 20

export type MergeCommaKeywordsResult = {
  value: string
  count: number
  truncated: boolean
}

/** Parse comma-separated keywords (trim, lowercase, de-dupe, preserve order). */
export function parseCommaKeywords(value: string): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const part of value.split(",")) {
    const lower = part.trim().toLowerCase()
    if (!lower || seen.has(lower)) continue
    seen.add(lower)
    out.push(lower)
  }
  return out
}

/** Merge comma-separated keywords (case-insensitive de-dupe), capped at ``max``. */
export function mergeCommaKeywords(
  current: string,
  toAdd: string[],
  max: number = CAREER_WATCH_MAX_KEYWORDS,
): MergeCommaKeywordsResult {
  const merged = parseCommaKeywords(current)
  for (const raw of toAdd) {
    const lower = raw.trim().toLowerCase()
    if (!lower || merged.includes(lower)) continue
    merged.push(lower)
  }
  const truncated = merged.length > max
  const capped = truncated ? merged.slice(0, max) : merged
  return {
    value: capped.join(", "),
    count: capped.length,
    truncated,
  }
}

function friendlyApiErrorMessage(bodyText: string): string | null {
  try {
    const parsed = JSON.parse(bodyText) as {
      detail?: { message?: string; code?: string } | string | Array<{ msg?: string; loc?: unknown[]; type?: string }>
    }
    const detail = parsed.detail
    if (detail && typeof detail === "object" && !Array.isArray(detail) && typeof detail.message === "string") {
      return detail.message
    }
    if (typeof detail === "string") {
      return detail
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0]
      const loc = Array.isArray(first?.loc) ? first.loc.map(String) : []
      if (loc.includes("keywords") && first?.type === "too_long") {
        return `You can use at most ${CAREER_WATCH_MAX_KEYWORDS} keywords. Remove one or more and try again.`
      }
      if (typeof first?.msg === "string") {
        return first.msg
      }
    }
  } catch {
    /* fall through */
  }
  return null
}

function alertSortTimestamp(alert: CareerWatchAlert): number {
  const raw = alert.notified_at ?? alert.created_at
  const ms = new Date(raw).getTime()
  return Number.isNaN(ms) ? 0 : ms
}

/** Sort Career Watch alerts for the dashboard list (client-side). */
export function sortCareerWatchAlerts(
  alerts: CareerWatchAlert[],
  mode: CareerAlertSort,
): CareerWatchAlert[] {
  const copy = [...alerts]
  if (mode === "match") {
    copy.sort((a, b) => {
      const sa = a.match_score ?? -1
      const sb = b.match_score ?? -1
      if (sb !== sa) return sb - sa
      return alertSortTimestamp(b) - alertSortTimestamp(a)
    })
    return copy
  }
  copy.sort((a, b) => alertSortTimestamp(b) - alertSortTimestamp(a))
  return copy
}

async function apiFetch<T>(
  path: string,
  token: string,
  init?: RequestInit,
): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init?.headers ?? {}),
    },
  })
  if (!resp.ok) {
    const bodyText = await resp.text()
    const friendlyMessage = friendlyApiErrorMessage(bodyText)
    throw new Error(
      friendlyMessage ?? "Something went wrong. Please check the details and try again.",
    )
  }
  if (resp.status === 204) {
    return undefined as T
  }
  return resp.json() as Promise<T>
}

export async function getCareerWatchLimits(token: string): Promise<CareerWatchLimits> {
  return apiFetch("/api/career-watch/limits", token)
}

export async function getCareerWatchKeywordSuggestions(
  token: string,
): Promise<string[]> {
  const data = await apiFetch<{ keywords: string[] }>(
    "/api/career-watch/keyword-suggestions",
    token,
  )
  return data.keywords
}

export async function detectCareersPage(
  token: string,
  careersPageUrl: string,
): Promise<DetectResult> {
  return apiFetch("/api/career-watch/detect", token, {
    method: "POST",
    body: JSON.stringify({ careers_page_url: careersPageUrl }),
  })
}

export async function listCareerWatches(token: string): Promise<CareerWatchEntry[]> {
  return apiFetch("/api/career-watch/watches", token)
}

export async function createCareerWatch(
  token: string,
  body: { careers_page_url: string; company_name?: string; keywords: string[] },
): Promise<CareerWatchEntry> {
  return apiFetch("/api/career-watch/watches", token, {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export async function updateCareerWatchKeywords(
  token: string,
  watchId: string,
  keywords: string[],
): Promise<CareerWatchEntry> {
  return apiFetch(`/api/career-watch/watches/${watchId}`, token, {
    method: "PATCH",
    body: JSON.stringify({ keywords }),
  })
}

export async function deleteCareerWatch(token: string, watchId: string): Promise<void> {
  await apiFetch(`/api/career-watch/watches/${watchId}`, token, { method: "DELETE" })
}

export async function listCareerAlerts(token: string): Promise<CareerWatchAlert[]> {
  return apiFetch("/api/career-watch/alerts", token)
}

export async function dismissCareerAlert(token: string, alertId: string): Promise<void> {
  await apiFetch(`/api/career-watch/alerts/${alertId}/dismiss`, token, {
    method: "POST",
  })
}

export async function clearCareerWatchInAppNotifications(
  token: string,
): Promise<{ cleared: number }> {
  return apiFetch("/api/career-watch/alerts/clear-in-app-notifications", token, {
    method: "POST",
  })
}

export async function dismissCareerAlertsBulk(
  token: string,
  body: { alert_ids?: string[]; dismiss_all?: boolean },
): Promise<{ dismissed: number }> {
  return apiFetch("/api/career-watch/alerts/dismiss", token, {
    method: "POST",
    body: JSON.stringify({
      alert_ids: body.alert_ids ?? [],
      dismiss_all: Boolean(body.dismiss_all),
    }),
  })
}
