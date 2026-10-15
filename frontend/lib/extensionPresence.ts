export const FLINT_APPLY_WEB_SOURCE = "flintapply-web";
export const FLINT_EXTENSION_SOURCE = "flint-extension";
export const FLINT_EXTENSION_PRESENCE_REQUEST = "FLINT_EXTENSION_PRESENCE_REQUEST";
export const FLINT_EXTENSION_PRESENCE_RESPONSE = "FLINT_EXTENSION_PRESENCE_RESPONSE";

export function pingFlintApplyExtension(options?: { timeoutMs?: number }): Promise<boolean> {
  const timeoutMs = options?.timeoutMs ?? 400;
  if (typeof window === "undefined") {
    return Promise.resolve(false);
  }

  const requestId =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random()}`;

  return new Promise((resolve) => {
    let settled = false;
    const finish = (detected: boolean) => {
      if (settled) return;
      settled = true;
      window.removeEventListener("message", onMessage);
      clearTimeout(timer);
      resolve(detected);
    };

    const onMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) return;
      if (event.source !== window) return;
      const data = event.data;
      if (!data || typeof data !== "object") return;
      const record = data as Record<string, unknown>;
      if (record.source !== FLINT_EXTENSION_SOURCE) return;
      if (record.type !== FLINT_EXTENSION_PRESENCE_RESPONSE) return;
      if (record.requestId !== requestId) return;
      finish(true);
    };

    window.addEventListener("message", onMessage);
    window.postMessage(
      {
        source: FLINT_APPLY_WEB_SOURCE,
        type: FLINT_EXTENSION_PRESENCE_REQUEST,
        requestId,
      },
      window.location.origin,
    );

    const timer = setTimeout(() => finish(false), timeoutMs);
  });
}
