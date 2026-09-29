/**
 * Classify /session/new JD-load failures so every path shows a specific,
 * actionable message instead of a silent blank textarea (invariant I6).
 */
import { ApiError } from "@/lib/api";
import { ExtensionJobDescriptionError } from "@/lib/extensionJobDescription";

export type JdLoadErrorKind =
  | "unauthorized"
  | "not_found"
  | "empty"
  | "network"
  | "server_error";

export interface JdLoadError {
  kind: JdLoadErrorKind;
  message: string;
}

const UNAUTHORIZED_MESSAGE =
  "Your session expired before this job could load. Sign in again and we'll bring you right back to it.";
// The backend intentionally returns a generic 404 for both "deleted" and
// "belongs to a different account" (I1 — no ownership-filter leak), so the
// two causes cannot be distinguished client-side. This message covers both.
const NOT_FOUND_MESSAGE =
  "We couldn't find this job under your signed-in account. It may have been saved from a different account, or the link may have expired.";
const EMPTY_MESSAGE =
  "We captured this job but not its text. Paste the description below, or re-capture it from the browser extension.";
const NETWORK_MESSAGE =
  "We couldn't reach the server to load this job. Check your connection and try again, or paste the description below.";
const SERVER_ERROR_MESSAGE =
  "Something went wrong loading this job. Try again, or paste the description below.";

/** Every JD-fetch failure classifies to a specific, non-empty message. */
export function classifyJdLoadError(err: unknown): JdLoadError {
  if (err instanceof ExtensionJobDescriptionError || err instanceof ApiError) {
    if (err.status === 401) return { kind: "unauthorized", message: UNAUTHORIZED_MESSAGE };
    if (err.status === 404) return { kind: "not_found", message: NOT_FOUND_MESSAGE };
    return { kind: "server_error", message: SERVER_ERROR_MESSAGE };
  }
  // fetch() itself threw (offline, DNS, CORS, aborted) — not an HTTP status.
  return { kind: "network", message: NETWORK_MESSAGE };
}

export const EMPTY_JD_TEXT_ERROR: JdLoadError = { kind: "empty", message: EMPTY_MESSAGE };
