"use client";

import Link from "next/link";
import { GraduationCap, Loader2 } from "lucide-react";
import { useRequireAuth } from "@/lib/auth/guards";
import { GUIDANCE_CONTENT } from "@/lib/guidance/content";
import { GUIDE_TOPIC_GROUPS } from "@/lib/guidance/guideTopics";

export default function GuidePage() {
  const { status } = useRequireAuth("/guide");

  if (status === "loading") {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <Link
        href="/dashboard"
        className="text-sm text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-300"
      >
        ← Back to dashboard
      </Link>
      <h1 className="mt-4 mb-2 flex items-center gap-2 text-2xl font-semibold text-slate-900 dark:text-white">
        <GraduationCap className="h-7 w-7 text-amber-700 dark:text-amber-400" aria-hidden />
        Guide
      </h1>
      <p className="mb-8 text-sm text-slate-600 dark:text-slate-400">
        Every tip FlintApply can show during setup, in one place — browse without replaying pop-ups.
        Turn pop-ups off under Settings → Tutorial tips.
      </p>

      {GUIDE_TOPIC_GROUPS.map((group) => (
        <section key={group.label} className="mb-10">
          <h2 className="mb-3 font-medium text-slate-800 dark:text-slate-200">{group.label}</h2>
          <div className="space-y-3">
            {group.steps.map((id) => {
              const c = GUIDANCE_CONTENT[id];
              return (
                <div
                  key={id}
                  className="rounded-xl border border-slate-200 p-4 dark:border-slate-800"
                  data-testid={`guide-step-${id}`}
                >
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white">{c.title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                    {c.guideBody ?? c.body}
                  </p>
                  {c.learnMoreHref ? (
                    <Link
                      href={c.learnMoreHref}
                      className="mt-2 inline-block text-sm font-medium text-amber-800 hover:underline dark:text-amber-300"
                    >
                      {c.learnMoreLabel ?? "Learn more"} →
                    </Link>
                  ) : null}
                </div>
              );
            })}
          </div>
        </section>
      ))}
    </main>
  );
}
