import { PRIVACY_EMAIL, PRODUCT_NAME } from "@/lib/brand";

/** In-app install guide — linked from dashboard, nav, and settings. */
export const EXTENSION_INSTALL_PATH = "/extension" as const;

export function chromeWebStoreUrl(): string | null {
  const url = process.env.NEXT_PUBLIC_CHROME_WEB_STORE_URL?.trim();
  return url || null;
}

/** Hosted .zip for private beta (unpacked load in Chrome). */
export function extensionBetaDownloadUrl(): string | null {
  const url = process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL?.trim();
  return url || null;
}

export type ExtensionInstallMode = "store" | "download" | "beta-manual";

export function extensionInstallMode(): ExtensionInstallMode {
  if (chromeWebStoreUrl()) return "store";
  if (extensionBetaDownloadUrl()) return "download";
  return "beta-manual";
}

export function extensionInstallHeadline(): string {
  return `${PRODUCT_NAME} browser extension`;
}

export function extensionBetaSupportLine(): string {
  return `Private beta builds are installed manually in Chrome. If you do not have a download link yet, email ${PRIVACY_EMAIL} from the address on your account and ask for the beta extension zip.`;
}
