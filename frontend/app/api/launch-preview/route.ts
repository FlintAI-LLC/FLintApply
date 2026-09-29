import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { previewCookieValue, PREVIEW_COOKIE_NAME } from "@/lib/launchPreview";

const COOKIE_MAX_AGE = 60 * 60 * 24 * 30; // 30 days

export async function POST(req: NextRequest) {
  const secret = process.env.LAUNCH_PREVIEW_SECRET?.trim();
  if (!secret) {
    return NextResponse.json(
      { code: "preview_disabled", message: "Early access is not configured." },
      { status: 503 },
    );
  }

  let key = "";
  const contentType = req.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    const body = (await req.json()) as { key?: string };
    key = (body.key ?? "").trim();
  } else {
    const form = await req.formData();
    key = String(form.get("key") ?? "").trim();
  }

  if (key !== secret) {
    return NextResponse.json(
      { code: "invalid_preview_key", message: "Invalid early-access code." },
      { status: 403 },
    );
  }

  const store = await cookies();
  const isProd = process.env.NODE_ENV === "production";
  store.set(PREVIEW_COOKIE_NAME, previewCookieValue(secret), {
    httpOnly: true,
    secure: isProd,
    sameSite: "lax",
    path: "/",
    maxAge: COOKIE_MAX_AGE,
    ...(isProd ? { domain: ".flintapply.com" } : {}),
  });

  return NextResponse.json({ ok: true });
}

/** Bookmarkable early-access link: /api/launch-preview?key=… */
export async function GET(req: NextRequest) {
  const secret = process.env.LAUNCH_PREVIEW_SECRET?.trim();
  const key = req.nextUrl.searchParams.get("key")?.trim() ?? "";
  const origin = req.nextUrl.origin;

  if (!secret || key !== secret) {
    return NextResponse.redirect(new URL("/launch-preview?error=1", origin));
  }

  const store = await cookies();
  const isProd = process.env.NODE_ENV === "production";
  store.set(PREVIEW_COOKIE_NAME, previewCookieValue(secret), {
    httpOnly: true,
    secure: isProd,
    sameSite: "lax",
    path: "/",
    maxAge: COOKIE_MAX_AGE,
    ...(isProd ? { domain: ".flintapply.com" } : {}),
  });

  return NextResponse.redirect(new URL("/?preview=ok", origin));
}
