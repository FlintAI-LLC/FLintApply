"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  formatLaunchCountdown,
  formatLaunchDatePacific,
  isLaunchOpen,
  launchAtFromEnv,
  msUntilLaunch,
} from "@/lib/launch";

function SatinBow() {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      className="launch-satin-bow"
      src="/marketing/launch-ribbon-bow.png"
      alt=""
      width={523}
      height={288}
      aria-hidden
    />
  );
}

export function LaunchCountdownRibbon({
  washed = false,
}: {
  washed?: boolean;
}) {
  const launchAt = launchAtFromEnv(process.env.NEXT_PUBLIC_LAUNCH_AT);
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    if (!launchAt || isLaunchOpen(new Date(), launchAt)) return;
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, [launchAt]);

  if (!launchAt || isLaunchOpen(now, launchAt)) {
    return null;
  }

  const remaining = msUntilLaunch(now, launchAt);

  return (
    <div
      className={
        washed
          ? "launch-satin-ribbon launch-satin-ribbon--washed"
          : "launch-satin-ribbon"
      }
      role="status"
      aria-live="polite"
    >
      <div className="relative">
        <div className="launch-satin-band" aria-hidden />
        <div className="launch-satin-row relative mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 sm:px-8">
          <div className="min-w-0">
            <p className="text-xs font-semibold tracking-wide sm:text-sm">
              FlintApply launches in{" "}
              <span className="tabular-nums">
                {formatLaunchCountdown(remaining)}
              </span>
            </p>
            <p className="text-[11px] font-medium">
              {formatLaunchDatePacific(launchAt)}
              <span aria-hidden> · </span>
              <Link
                href="/launch-preview"
                className="font-semibold underline underline-offset-4"
              >
                Early access invite
              </Link>
            </p>
          </div>
          <SatinBow />
        </div>
      </div>
    </div>
  );
}
