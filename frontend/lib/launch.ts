/** Public launch instant (Pacific). Override with NEXT_PUBLIC_LAUNCH_AT (ISO-8601). */
export const DEFAULT_LAUNCH_AT_ISO = "2026-10-01T09:00:00-07:00";

export function launchAtFromEnv(
  raw?: string | null,
): Date | null {
  const value = (raw ?? process.env.NEXT_PUBLIC_LAUNCH_AT ?? DEFAULT_LAUNCH_AT_ISO).trim();
  if (!value) return null;
  const ms = Date.parse(value);
  if (Number.isNaN(ms)) return null;
  return new Date(ms);
}

export function isLaunchOpen(now: Date, launchAt: Date | null): boolean {
  if (!launchAt) return true;
  return now.getTime() >= launchAt.getTime();
}

export function msUntilLaunch(now: Date, launchAt: Date | null): number {
  if (!launchAt) return 0;
  return Math.max(0, launchAt.getTime() - now.getTime());
}

export function formatLaunchCountdown(ms: number): string {
  if (ms <= 0) return "Launching now";
  const totalSec = Math.floor(ms / 1000);
  const days = Math.floor(totalSec / 86400);
  const hours = Math.floor((totalSec % 86400) / 3600);
  const minutes = Math.floor((totalSec % 3600) / 60);
  const seconds = totalSec % 60;
  if (days > 0) {
    return `${days}d ${hours}h ${minutes}m`;
  }
  if (hours > 0) {
    return `${hours}h ${minutes}m ${seconds}s`;
  }
  return `${minutes}m ${seconds}s`;
}

export function formatLaunchDatePacific(launchAt: Date): string {
  return launchAt.toLocaleString("en-US", {
    timeZone: "America/Los_Angeles",
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}
