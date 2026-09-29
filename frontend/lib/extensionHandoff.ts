/** Persist extension JD handoff across auth / onboarding redirects. */

const HANDOFF_KEY = "sr_extension_jd_handoff"
const CONSUMED_KEY = "sr_extension_jd_handoff_consumed"

/** A handoff older than this never hijacks a later run — capture, not carry-over (defect #6/#10). */
export const EXTENSION_HANDOFF_TTL_MS = 30 * 60 * 1000

interface ConsumedMarker {
  jd_id: string
  consumed_at: number
}

function readConsumedMarker(): ConsumedMarker | null {
  if (typeof window === "undefined") return null
  try {
    const raw = sessionStorage.getItem(CONSUMED_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as ConsumedMarker
    if (!parsed?.jd_id || typeof parsed.consumed_at !== "number") return null
    if (Date.now() - parsed.consumed_at > EXTENSION_HANDOFF_TTL_MS) return null
    return parsed
  } catch {
    return null
  }
}

/** True once `markExtensionHandoffConsumed` has recorded this exact jd_id. */
export function isExtensionHandoffConsumed(jdId: string): boolean {
  return readConsumedMarker()?.jd_id === jdId
}

/**
 * Record that this jd_id has been fully consumed (JD loaded into the wizard,
 * or a permanent 404). The URL — not sessionStorage — is the durable carrier
 * of jd_id: every step transition and JD-load re-render re-derives a handoff
 * from it, so `saveExtensionHandoff` must refuse to re-persist the SAME
 * jd_id once it is marked consumed, or the handoff resurrects itself the
 * instant the URL is touched again (AC9).
 */
export function markExtensionHandoffConsumed(jdId: string): void {
  if (typeof window === "undefined") return
  sessionStorage.setItem(
    CONSUMED_KEY,
    JSON.stringify({ jd_id: jdId, consumed_at: Date.now() } satisfies ConsumedMarker),
  )
}

export interface ExtensionHandoff {
  jd_id: string
  source: string
  step: string
  jd_review?: boolean
  /** epoch ms this handoff was captured; drives EXTENSION_HANDOFF_TTL_MS expiry. */
  captured_at?: number
}

export function saveExtensionHandoff(handoff: ExtensionHandoff): void {
  if (typeof window === "undefined") return
  // Once this jd_id is consumed, every later re-derivation from the URL
  // must be a no-op (AC9) — see markExtensionHandoffConsumed.
  if (isExtensionHandoffConsumed(handoff.jd_id)) return
  // Only extension-sourced handoffs are durable across auth/onboarding. An
  // in-app "jobs" link replaces the URL with source=jobs; persisting that
  // would make ExtensionHandoffBanner claim extension provenance for a job
  // saved entirely in-app (S3).
  if (handoff.source !== "extension") return
  const stamped: ExtensionHandoff = {
    ...handoff,
    captured_at: handoff.captured_at ?? Date.now(),
  }
  sessionStorage.setItem(HANDOFF_KEY, JSON.stringify(stamped))
}

export function getExtensionHandoff(): ExtensionHandoff | null {
  if (typeof window === "undefined") return null
  try {
    const raw = sessionStorage.getItem(HANDOFF_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as ExtensionHandoff
    if (!parsed?.jd_id) return null
    if (
      typeof parsed.captured_at === "number" &&
      Date.now() - parsed.captured_at > EXTENSION_HANDOFF_TTL_MS
    ) {
      // Stale — clear so it cannot hijack a later tailoring run or leave the
      // dashboard banner up forever.
      clearExtensionHandoff()
      return null
    }
    return {
      jd_id: parsed.jd_id,
      source: parsed.source ?? "extension",
      step: parsed.step ?? "jd",
      jd_review: parsed.jd_review,
      captured_at: parsed.captured_at,
    }
  } catch {
    return null
  }
}

export function clearExtensionHandoff(): void {
  if (typeof window === "undefined") return
  sessionStorage.removeItem(HANDOFF_KEY)
}

/** Parse jd_id/source/step from a path+query string or full URL. */
export function parseExtensionHandoffFromUrl(urlOrPath: string): ExtensionHandoff | null {
  try {
    const base =
      typeof window !== "undefined" ? window.location.origin : "http://localhost"
    const parsed = urlOrPath.startsWith("http")
      ? new URL(urlOrPath)
      : new URL(urlOrPath, base)
    const jdId = parsed.searchParams.get("jd_id")
    if (!jdId) return null
    return {
      jd_id: jdId,
      source: parsed.searchParams.get("source") ?? "extension",
      step: parsed.searchParams.get("step") ?? "jd",
      jd_review: parsed.searchParams.get("jd_review") === "1",
    }
  } catch {
    return null
  }
}

export function captureExtensionHandoffFromUrl(urlOrPath: string): ExtensionHandoff | null {
  const handoff = parseExtensionHandoffFromUrl(urlOrPath)
  if (handoff) saveExtensionHandoff(handoff)
  return handoff
}

export function captureExtensionHandoffFromParams(
  params: Pick<URLSearchParams, "get">,
): ExtensionHandoff | null {
  const jdId = params.get("jd_id")
  if (!jdId) return null
  const handoff: ExtensionHandoff = {
    jd_id: jdId,
    source: params.get("source") ?? "extension",
    step: params.get("step") ?? "jd",
    jd_review: params.get("jd_review") === "1",
  }
  saveExtensionHandoff(handoff)
  return handoff
}

export function buildSessionNewUrl(handoff: ExtensionHandoff): string {
  const params = new URLSearchParams({
    step: handoff.step,
    jd_id: handoff.jd_id,
    source: handoff.source,
  })
  if (handoff.jd_review) params.set("jd_review", "1")
  return `/session/new?${params.toString()}`
}

/** Avoid router.replace when the wizard URL already matches (prevents UI flash). */
export function replaceSessionNewUrlIfNeeded(
  router: { replace: (url: string) => void },
  handoff: ExtensionHandoff,
): void {
  const target = buildSessionNewUrl(handoff)
  if (typeof window !== "undefined") {
    const current = `${window.location.pathname}${window.location.search}`
    if (current === target) return
  }
  router.replace(target)
}
