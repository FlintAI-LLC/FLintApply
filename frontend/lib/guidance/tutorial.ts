/** Tutorial toggle + per-step acknowledgment (localStorage only — no PII). */

const TUTORIAL_ENABLED_KEY = "flintapply.tutorial_enabled";
const GUIDANCE_PREFIX = "guidance.";

function getStorage(): Storage | null {
  if (typeof window !== "undefined" && window.localStorage) {
    return window.localStorage;
  }
  const g = globalThis as { localStorage?: Storage };
  if (g.localStorage) return g.localStorage;
  return null;
}

export function isTutorialEnabled(): boolean {
  const storage = getStorage();
  if (!storage) return true;
  return storage.getItem(TUTORIAL_ENABLED_KEY) !== "false";
}

export function setTutorialEnabled(enabled: boolean): void {
  const storage = getStorage();
  if (!storage) return;
  storage.setItem(TUTORIAL_ENABLED_KEY, enabled ? "true" : "false");
}

export function isGuidanceSeen(stepKey: string): boolean {
  const storage = getStorage();
  if (!storage) return true;
  return storage.getItem(`${GUIDANCE_PREFIX}${stepKey}`) === "1";
}

export function markGuidanceSeen(stepKey: string): void {
  const storage = getStorage();
  if (!storage) return;
  storage.setItem(`${GUIDANCE_PREFIX}${stepKey}`, "1");
}

export function restartTutorial(): void {
  const storage = getStorage();
  if (!storage) return;
  const keys: string[] = [];
  for (let i = 0; i < storage.length; i++) {
    const k = storage.key(i);
    if (k?.startsWith(GUIDANCE_PREFIX)) keys.push(k);
  }
  for (const k of keys) storage.removeItem(k);
}
