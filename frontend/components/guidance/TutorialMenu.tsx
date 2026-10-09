"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { GraduationCap } from "lucide-react";
import { clsx } from "clsx";
import {
  isTutorialEnabled,
  restartTutorial,
  setTutorialEnabled,
} from "@/lib/guidance/tutorial";

type TutorialMenuProps = {
  /** Icon-only control (e.g. nav bar next to theme toggle). */
  showLabel?: boolean;
};

export function TutorialMenu({ showLabel = true }: TutorialMenuProps) {
  const [enabled, setEnabled] = useState(true);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setEnabled(isTutorialEnabled());
  }, []);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={clsx(
          "flex items-center justify-center text-xs font-medium rounded-lg border transition-colors",
          showLabel ? "gap-1.5 px-2 py-1.5" : "p-1.5",
          enabled
            ? "border-amber-400/50 text-amber-800 dark:text-amber-300 bg-amber-50/80 dark:bg-amber-950/30"
            : "border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-400",
        )}
        aria-expanded={open}
        aria-haspopup="true"
        aria-label="Tutorial tips"
        title="Tutorial tips"
      >
        <GraduationCap className="w-4 h-4 shrink-0" aria-hidden />
        {showLabel ? <span className="hidden sm:inline">Tutorial</span> : null}
      </button>
      {open && (
        <div
          className="absolute right-0 top-full mt-1 w-56 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-lg p-3 z-[90] text-sm space-y-3"
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
          <Link
            href="/guide"
            className="block w-full text-left text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white text-xs"
            onClick={() => setOpen(false)}
          >
            Browse all tips
          </Link>
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
