"use client";

import { useCallback, useEffect, useState } from "react";
import type { GuidanceStepId } from "@/lib/guidance/content";
import { markGuidanceSeen } from "@/lib/guidance/tutorial";

/** Show contextual tutorial modals; chains to the next unseen step after acknowledge. */
export function useGuidanceModal(
  pickStep: () => GuidanceStepId | null,
  enabled = true,
) {
  const [guidanceStep, setGuidanceStep] = useState<GuidanceStepId | null>(null);

  const refresh = useCallback(() => {
    if (!enabled) return;
    const step = pickStep();
    if (step) setGuidanceStep(step);
  }, [enabled, pickStep]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const onAcknowledge = useCallback(() => {
    if (guidanceStep) markGuidanceSeen(guidanceStep);
    setGuidanceStep(null);
    if (!enabled) return;
    window.setTimeout(() => {
      const next = pickStep();
      if (next) setGuidanceStep(next);
    }, 0);
  }, [guidanceStep, enabled, pickStep]);

  return { guidanceStep, onAcknowledge, refresh };
}
