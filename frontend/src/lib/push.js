// Call alerts through web push: whether this browser can take them, and turning them on.
import { api } from "@/api/client";

const DISMISSED = "call-alerts-dismissed";

export const pushSupported = () =>
  typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

/** An iPhone or iPad browser tab, where alerts work only from the Home Screen app (iOS 16.4+). */
export const needsHomeScreen = () =>
  /iPhone|iPad|iPod/.test(navigator.userAgent) && !window.matchMedia("(display-mode: standalone)").matches;

export function dismissed() {
  try { return localStorage.getItem(DISMISSED) === "1"; } catch { return false; }
}

export function dismiss() {
  try { localStorage.setItem(DISMISSED, "1"); } catch { /* private mode keeps nothing */ }
}

/** Whether this device already sends alerts to the signed-in login. */
export async function subscribed() {
  if (!pushSupported()) return false;
  const reg = await navigator.serviceWorker.getRegistration();
  return Boolean(reg && (await reg.pushManager.getSubscription()));
}

function keyBytes(base64) {
  const padded = (base64 + "=".repeat((4 - (base64.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  return Uint8Array.from(atob(padded), (c) => c.charCodeAt(0));
}

/** Ask permission, subscribe this device and tell the server; throws with a reason on refusal. */
export async function enableAlerts(publicKey) {
  if ((await Notification.requestPermission()) !== "granted") {
    throw new Error("Alerts are blocked for this site. Allow notifications in the browser settings.");
  }
  const reg = await navigator.serviceWorker.ready;
  const subscription =
    (await reg.pushManager.getSubscription()) ||
    (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(publicKey) }));
  const { endpoint, keys } = subscription.toJSON();
  await api("/push/subscribe/", { method: "POST", body: { endpoint, keys: { p256dh: keys.p256dh, auth: keys.auth } } });
}
