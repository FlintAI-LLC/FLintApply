import type { NextResponse } from "next/server"

const RETURN_URL_KEY = "sr_auth_return_url"

/** Survives OAuth when sessionStorage is unavailable to middleware (edge proxy). */
export const AUTH_RETURN_COOKIE = "sr_auth_return_path"
const AUTH_RETURN_COOKIE_MAX_AGE = 60 * 30

/** Reject open redirects; only same-origin relative paths. */
export function safeReturnPath(raw: string | null, fallback = "/dashboard"): string {
  const value = (raw ?? "").trim()
  if (
    !value.startsWith("/") ||
    value.startsWith("//") ||
    value.includes("\\") ||
    value.includes(":") ||
    // WHATWG URL parsing strips C0 controls before parsing a path, so
    // "/\t/evil.com" resolves to "https://evil.com/" despite passing every
    // check above. Reject them outright rather than only at position 1.
    /[\x00-\x1F\x7F]/.test(value)
  ) {
    return fallback
  }
  return value
}

/** Remember where to return after sign-in (survives OAuth round-trips). */
export function saveAuthReturnUrl(path?: string): void {
  if (typeof window === "undefined") return
  const target = path ?? `${window.location.pathname}${window.location.search}`
  if (!target || target.startsWith("/auth")) return
  sessionStorage.setItem(RETURN_URL_KEY, target)
}

/**
 * Prefer explicit callbackUrl, then stored return path, then fallback.
 * Both branches carry attacker-controlled values (a query param and a
 * sessionStorage write from an earlier, unvalidated saveAuthReturnUrl call)
 * and must be re-validated here — this is the only chokepoint both
 * callbackUrl-based and stored-path-based callers share.
 */
export function resolveAuthReturnUrl(
  callbackUrlFromQuery: string | null | undefined,
  fallback = "/dashboard",
): string {
  if (callbackUrlFromQuery && callbackUrlFromQuery !== "/auth") {
    return safeReturnPath(callbackUrlFromQuery, fallback)
  }
  if (typeof window === "undefined") return fallback
  const stored = sessionStorage.getItem(RETURN_URL_KEY)
  if (stored && !stored.startsWith("/auth")) {
    sessionStorage.removeItem(RETURN_URL_KEY)
    return safeReturnPath(stored, fallback)
  }
  return fallback
}

export function readAuthReturnCookie(raw: string | undefined): string | null {
  if (!raw?.trim()) return null
  const path = safeReturnPath(raw.trim(), "")
  return path || null
}

export function setAuthReturnCookie(response: NextResponse, returnPath: string): void {
  const safe = safeReturnPath(returnPath, "")
  if (!safe) return
  response.cookies.set(AUTH_RETURN_COOKIE, safe, {
    path: "/",
    maxAge: AUTH_RETURN_COOKIE_MAX_AGE,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    httpOnly: false,
  })
}

export function clearAuthReturnCookie(response: NextResponse): void {
  response.cookies.set(AUTH_RETURN_COOKIE, "", {
    path: "/",
    maxAge: 0,
  })
}
