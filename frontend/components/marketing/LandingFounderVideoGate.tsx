"use client";

import { useEffect, useState } from "react";
import { FounderVideoFullscreen } from "@/components/marketing/FounderVideoFullscreen";
import {
  INTRO_DISMISSED_EVENT,
  isFounderFirstRunComplete,
  markFounderFirstRunComplete,
  readIntroWillPlay,
} from "@/lib/marketing/founderVideo";

/**
 * First-run visitors: fullscreen founder video after brand intro (or immediately
 * if intro is skipped). Return visitors: renders nothing.
 */
export function LandingFounderVideoGate() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const forceFounder = params.get("founder") === "1";

    if (isFounderFirstRunComplete() && !forceFounder) {
      return;
    }

    const openFullscreen = () => setOpen(true);

    if (!readIntroWillPlay()) {
      openFullscreen();
      return;
    }

    window.addEventListener(INTRO_DISMISSED_EVENT, openFullscreen);
    return () => {
      window.removeEventListener(INTRO_DISMISSED_EVENT, openFullscreen);
    };
  }, []);

  const dismiss = () => {
    markFounderFirstRunComplete();
    setOpen(false);
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
  };

  if (!open) return null;

  return <FounderVideoFullscreen onDismiss={dismiss} />;
}
