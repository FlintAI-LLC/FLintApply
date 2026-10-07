"use client";

import { useEffect, useState } from "react";
import { GraduationCap } from "lucide-react";
import { clsx } from "clsx";
import {
  isTutorialEnabled,
  restartTutorial,
  setTutorialEnabled,
} from "@/lib/guidance/tutorial";

export function TutorialMenu() {
  const [enabled, setEnabled] = useState(true);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setEnabled(isTutorialEnabled());
  }, []);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={clsx(
          "flex items-center gap-1.5 text-xs font-medium px-2 py-1.5 rounded-lg border transition-colors",
          enabled
            ? "border-amber-400/50 text-amber-800 dark:text-amber-300 bg-amber-50/80 dark:bg-amber-950/30"
            : "border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-400",
        )}
        aria-expanded={open}
        aria-haspopup="true"
      >
        <GraduationCap className="w-3.5 h-3.5" aria-hidden />
        <span className="hidden sm:inline">Tutorial</span>
      </button>
      {open && (
        <div
          className="absolute right-0 top-full mt-1 w-56 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-lg p-3 z-50 text-sm space-y-3"
          role="menu"
        >
          <label className="flex items-center gap-2 cursor-pointer text-slate-800 dark:text-slate-200">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => {
                const next = e.target.checked;
                setTutorialEnabled(next);
                setEnabled(next);
              }}
              className="rounded border-slate-400 text-amber-600 focus:ring-amber-400"
            />
            Show step tips
          </label>
          <button
            type="button"
            className="w-full text-left text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white text-xs"
            onClick={() => {
              restartTutorial();
              setOpen(false);
            }}
          >
            Restart tutorial
          </button>
        </div>
      )}
    </div>
  );
}
