const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const VAPID_PUBLIC_BUILD = process.env.NEXT_PUBLIC_WEB_PUSH_VAPID_PUBLIC_KEY ?? "";

async function resolveVapidPublicKey(): Promise<string> {
  if (VAPID_PUBLIC_BUILD) return VAPID_PUBLIC_BUILD;
  const res = await fetch(`${BASE}/api/notifications/web-push/public-key`);
  if (!res.ok) {
    throw new Error("Web push is not configured (missing VAPID public key)");
  }
  const body = (await res.json()) as { public_key?: string };
  if (!body.public_key) {
    throw new Error("Web push is not configured (missing VAPID public key)");
  }
  return body.public_key;
}

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const arr = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
  return arr;
}

export async function registerWebPush(accessToken: string): Promise<boolean> {
  const vapidPublic = await resolveVapidPublicKey();
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    throw new Error("This browser does not support web push");
  }

  let permission = Notification.permission;
  if (permission === "default") {
    permission = await Notification.requestPermission();
  }
  if (permission === "denied") {
    throw new Error(
      "Notifications are blocked for flintapply.com. Open the lock icon in the address bar → Site settings → Notifications → Allow, then try again."
    );
  }
  if (permission !== "granted") {
    throw new Error("Notification permission was not granted. Choose Allow when the browser prompts you.");
  }

  let registration: ServiceWorkerRegistration;
  try {
    registration = await navigator.serviceWorker.register("/sw.js", {
      scope: "/",
    });
    await Promise.race([
      navigator.serviceWorker.ready,
      new Promise<never>((_, reject) => {
        window.setTimeout(
          () => reject(new Error("Service worker registration timed out. Hard-refresh and try again.")),
          20_000
        );
      }),
    ]);
  } catch (e) {
    const msg = e instanceof Error ? e.message : "Service worker failed";
    throw new Error(msg);
  }

  let subscription = await registration.pushManager.getSubscription();
  if (!subscription) {
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(vapidPublic) as unknown as BufferSource,
    });
  }

  const json = subscription.toJSON();
  const res = await fetch(`${BASE}/api/notifications/web-push/subscribe`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({
      endpoint: json.endpoint,
      expiration_time: json.expirationTime
        ? new Date(json.expirationTime).toISOString()
        : null,
      keys: json.keys,
      user_agent: navigator.userAgent,
      platform_hint: navigator.platform,
    }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Subscribe failed (${res.status})`);
  }
  return true;
}

export async function unregisterWebPush(accessToken: string): Promise<void> {
  const registration = await navigator.serviceWorker.getRegistration("/");
  const sub = await registration?.pushManager.getSubscription();
  if (sub) {
    await fetch(
      `${BASE}/api/notifications/web-push/subscribe?endpoint=${encodeURIComponent(sub.endpoint)}`,
      {
        method: "DELETE",
        headers: { Authorization: `Bearer ${accessToken}` },
      }
    );
    await sub.unsubscribe();
  }
}
