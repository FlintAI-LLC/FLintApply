import type { NextRequest } from "next/server";
import { isLaunchOpen, launchAtFromEnv } from "@/lib/launch";
import { PREVIEW_COOKIE_NAME, previewCookieValue } from "@/lib/launchPreview";

export function launchGateActive(): boolean {
  const launchAt = launchAtFromEnv(
    process.env.NEXT_PUBLIC_LAUNCH_AT ?? process.env.LAUNCH_AT,
  );
  return !isLaunchOpen(new Date(), launchAt);
}

export function hasLaunchPreviewAccess(req: NextRequest): boolean {
  const secret = process.env.LAUNCH_PREVIEW_SECRET?.trim();
  if (!secret) return false;
  const expected = previewCookieValue(secret);
  return req.cookies.get(PREVIEW_COOKIE_NAME)?.value === expected;
}
