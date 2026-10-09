"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import {
  recordProductBeacon,
  type ProductBeaconKey,
} from "@/lib/analytics/productBeacon";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

function metricForPath(pathname: string): ProductBeaconKey | null {
  if (pathname.startsWith("/admin")) return null;
  if (pathname === "/") return "landing_view";
  if (pathname === "/auth" || pathname.startsWith("/auth/")) return "auth_page_view";
  if (
    pathname.startsWith("/dashboard") ||
    pathname.startsWith("/session") ||
    pathname.startsWith("/jobs") ||
    pathname.startsWith("/profile") ||
    pathname.startsWith("/billing") ||
    pathname.startsWith("/career-watch")
  ) {
    return "web_app_view";
  }
  return null;
}

export function ProductAnalyticsBeacon() {
  const pathname = usePathname();

  useEffect(() => {
    const metric = metricForPath(pathname);
    if (metric) recordProductBeacon(metric, API_BASE);
  }, [pathname]);

  return null;
}
