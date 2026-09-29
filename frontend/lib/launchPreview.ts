import { createHmac } from "crypto";

export const PREVIEW_COOKIE_NAME = "sr_launch_preview";

const PREVIEW_COOKIE_PAYLOAD = "flintapply-launch-preview-v1";

/** HMAC cookie value — must match backend ``launch_gate.preview_cookie_value``. */
export function previewCookieValue(secret: string): string {
  return createHmac("sha256", secret)
    .update(PREVIEW_COOKIE_PAYLOAD)
    .digest("hex")
    .slice(0, 32);
}

export function isLaunchPublicPath(pathname: string): boolean {
  if (pathname === "/") return true;
  if (pathname === "/launch-preview") return true;
  if (pathname.startsWith("/legal")) return true;
  if (pathname.startsWith("/admin")) return true;
  if (pathname.startsWith("/api/launch-preview")) return true;
  return false;
}
