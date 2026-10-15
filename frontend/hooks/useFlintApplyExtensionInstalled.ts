"use client";

import { useCallback, useEffect, useState } from "react";
import { pingFlintApplyExtension } from "@/lib/extensionPresence";

/** Advisory extension presence for Score & Export apply CTA copy only. */
export function useFlintApplyExtensionInstalled(): boolean | null {
  const [detected, setDetected] = useState<boolean | null>(null);

  const runPing = useCallback(() => {
    void pingFlintApplyExtension({ timeoutMs: 400 }).then(setDetected);
  }, []);

  useEffect(() => {
    runPing();
  }, [runPing]);

  useEffect(() => {
    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        runPing();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [runPing]);

  return detected;
}
