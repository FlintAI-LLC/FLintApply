import { PRIVACY_EMAIL, PRODUCT_NAME } from "@/lib/brand";

/** In-app install guide — linked from dashboard, nav, and settings. */
export const EXTENSION_INSTALL_PATH = "/extension" as const;

const STORE_URL =
  "https://chromewebstore.google.com/detail/flint-apply/lcgioikkofajhechkhgjoidmbmnbniji";

const BETA_ZIP_PATH = "/downloads/flintapply-extension-beta.zip";

/**
 * Default extension version shown on /extension (store + beta labels).
 * Bump with every flint-extension release — keep in sync with
 * flint-extension/manifest.json `version`.
 */
export const EXTENSION_RELEASE_VERSION = "0.1.41";

/** True when the public site is the production deploy (Chrome Web Store is the install path). */
export function isProductionAppEnv(): boolean {
  return process.env.NEXT_PUBLIC_APP_ENV === "production";
}

function sanitizeChromeWebStoreUrl(raw: string | undefined): string {
  const candidate = raw?.trim() || STORE_URL;
  try {
    const parsed = new URL(candidate);
    if (parsed.protocol !== "https:") return STORE_URL;
    if (parsed.hostname !== "chromewebstore.google.com") return STORE_URL;
    if (!parsed.pathname.startsWith("/detail/")) return STORE_URL;
    return parsed.toString();
  } catch {
    return STORE_URL;
  }
}

function sanitizeBetaDownloadUrl(raw: string | undefined, siteOrigin: string): string | null {
  if (!raw?.trim()) return null;
  try {
    const parsed = new URL(raw.trim());
    if (parsed.protocol !== "https:") return null;
    const allowedHost = siteOrigin ? new URL(siteOrigin.replace(/\/$/, "")).hostname : "flintapply.com";
    if (parsed.hostname !== allowedHost) return null;
    if (!parsed.pathname.endsWith(".zip") || !parsed.pathname.includes("/downloads/")) {
      return null;
    }
    return parsed.toString();
  } catch {
    return null;
  }
}

export function chromeWebStoreUrl(): string | null {
  return sanitizeChromeWebStoreUrl(process.env.NEXT_PUBLIC_CHROME_WEB_STORE_URL);
}

/** Hosted .zip for latest extension (Developer mode). Available on production during CWS review lag. */
export function extensionBetaDownloadUrl(): string | null {
  if (process.env.NEXT_PUBLIC_EXTENSION_BETA_DOWNLOAD_ENABLED === "false") {
    return null;
  }
  const site = process.env.NEXT_PUBLIC_SITE_URL?.trim().replace(/\/$/, "") || "";
  const configured = sanitizeBetaDownloadUrl(
    process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL,
    site || "https://flintapply.com",
  );
  if (configured) return configured;
  if (site) {
    return `${site}${BETA_ZIP_PATH}`;
  }
  return null;
}

/** Version string for the public Chrome Web Store listing (may lag latest beta by a release). */
export function chromeWebStoreExtensionVersion(): string | null {
  const v = process.env.NEXT_PUBLIC_CHROME_WEB_STORE_EXTENSION_VERSION?.trim();
  return v || EXTENSION_RELEASE_VERSION;
}

/** Version string for the hosted beta .zip (latest engineering build). */
export function extensionBetaVersion(): string | null {
  const v = process.env.NEXT_PUBLIC_EXTENSION_BETA_VERSION?.trim();
  return v || EXTENSION_RELEASE_VERSION;
}

/** @deprecated Prefer checking store + beta URLs directly in the install guide. */
export type ExtensionInstallMode = "store" | "download" | "beta-manual";

export function extensionInstallMode(): ExtensionInstallMode {
  if (extensionBetaDownloadUrl()) return "download";
  if (chromeWebStoreUrl()) return "store";
  return "beta-manual";
}

export function extensionInstallHeadline(): string {
  return `${PRODUCT_NAME} browser extension`;
}

export function extensionBetaSupportLine(): string {
  return `Private beta builds are installed manually in Chrome. If the download link is unavailable, email ${PRIVACY_EMAIL} from the address on your account and ask for the beta extension zip.`;
}

/** Short copy when Store listing lags the engineering build (Chrome review). */
export function extensionChromeReviewGuidance(storeVersion: string | null, betaVersion: string | null): string {
  const store = storeVersion ?? "the Store build";
  const beta = betaVersion ?? EXTENSION_RELEASE_VERSION;
  return `While Chrome Web Store review is in progress (live listing v${store}), install the latest zip in Developer mode for autofill and other new fixes (v${beta}+). Review in the dashboard can show a higher version than what’s published yet.`;
}

/**
 * Prefer Developer-mode zip over Chrome Web Store when a beta download URL exists.
 * (Store listing often lags review; autofill requires the latest engineering build.)
 */
export function extensionBetaRecommendedOverStore(): boolean {
  if (process.env.NEXT_PUBLIC_EXTENSION_BETA_RECOMMENDED === "false") return false;
  return extensionBetaDownloadUrl() !== null;
}
