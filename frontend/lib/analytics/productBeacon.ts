/** Once-per-local-day anonymous surface counters (no cookies). */

const STORAGE_PREFIX = "sr_metric_beacon:";

export type ProductBeaconKey =
  | "landing_view"
  | "auth_page_view"
  | "web_app_view"
  | "extension_open";

function todayKey(): string {
  return new Date().toISOString().slice(0, 10);
}

function storageKey(metric: ProductBeaconKey): string {
  return `${STORAGE_PREFIX}${metric}:${todayKey()}`;
}

export function recordProductBeacon(metric: ProductBeaconKey, apiBase: string): void {
  if (typeof window === "undefined") return;
  try {
    if (sessionStorage.getItem(storageKey(metric))) return;
    sessionStorage.setItem(storageKey(metric), "1");
  } catch {
    // Private mode — still attempt the network call once per page load.
  }

  const base = apiBase.replace(/\/$/, "");
  void fetch(`${base}/api/public/metrics/beacon`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key: metric }),
    keepalive: true,
    credentials: "omit",
  }).catch(() => {
    /* best-effort */
  });
}
