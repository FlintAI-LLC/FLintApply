import { PRIVACY_EMAIL, PRODUCT_NAME } from "@/lib/brand";

/** In-app install guide — linked from dashboard, nav, and settings. */
export const EXTENSION_INSTALL_PATH = "/extension" as const;

const STORE_URL =
  "https://chromewebstore.google.com/detail/flint-apply/lcgioikkofajhechkhgjoidmbmnbniji";

const BETA_ZIP_PATH = "/downloads/flintapply-extension-beta.zip";

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

/** Hosted .zip for private beta (unpacked load in Chrome). Hidden on production. */
export function extensionBetaDownloadUrl(): string | null {
  if (isProductionAppEnv()) return null;
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

export function chromeWebStoreExtensionVersion(): string | null {
  const v = process.env.NEXT_PUBLIC_CHROME_WEB_STORE_EXTENSION_VERSION?.trim();
  return v || "0.1.35";
}

export function extensionBetaVersion(): string | null {
  const v = process.env.NEXT_PUBLIC_EXTENSION_BETA_VERSION?.trim();
  return v || "0.1.30";
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
