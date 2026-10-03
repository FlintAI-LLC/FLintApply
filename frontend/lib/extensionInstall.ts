import { PRIVACY_EMAIL, PRODUCT_NAME } from "@/lib/brand";

/** In-app install guide — linked from dashboard, nav, and settings. */
export const EXTENSION_INSTALL_PATH = "/extension" as const;

const STORE_URL =
  "https://chromewebstore.google.com/detail/flint-apply/lcgioikkofajhechkhgjoidmbmnbniji";

export function chromeWebStoreUrl(): string | null {
  const url = process.env.NEXT_PUBLIC_CHROME_WEB_STORE_URL?.trim();
  return url || STORE_URL;
}

/** Hosted .zip for private beta (unpacked load in Chrome). */
export function extensionBetaDownloadUrl(): string | null {
  const configured = process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL?.trim();
  if (configured) return configured;
  const site = process.env.NEXT_PUBLIC_SITE_URL?.trim() || "";
  if (site) {
    return `${site.replace(/\/$/, "")}/downloads/flintapply-extension-beta.zip`;
  }
  return null;
}

export function chromeWebStoreExtensionVersion(): string | null {
  const v = process.env.NEXT_PUBLIC_CHROME_WEB_STORE_EXTENSION_VERSION?.trim();
  return v || "0.1.28";
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
