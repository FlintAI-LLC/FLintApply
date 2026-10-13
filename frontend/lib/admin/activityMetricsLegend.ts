/** Copy for admin Reports → Usage & traffic chart (matches backend activity metrics). */

export type ActivityMetricLegendItem = {
  id: string;
  label: string;
  description: string;
};

export const ACTIVITY_METRICS_LEGEND: ActivityMetricLegendItem[] = [
  {
    id: "dau",
    label: "DAU (all)",
    description:
      "Distinct users with at least one successful login that day (web app or Chrome extension).",
  },
  {
    id: "dau_web",
    label: "DAU web",
    description: "Distinct users who logged in through the web app that day.",
  },
  {
    id: "dau_extension",
    label: "DAU extension",
    description: "Distinct users who logged in through the Chrome extension that day.",
  },
  {
    id: "wau",
    label: "WAU",
    description:
      "Distinct users with at least one login in the 7 calendar days ending on that date (rolling window).",
  },
  {
    id: "mau",
    label: "MAU",
    description:
      "Distinct users with at least one login in the 30 calendar days ending on that date (rolling window).",
  },
  {
    id: "new_registrations",
    label: "Registrations",
    description: "New user accounts created that day.",
  },
  {
    id: "landing_views",
    label: "Landing views",
    description:
      "Anonymous views of the public landing page (marketing beacon). Not tied to logins or signups.",
  },
];
