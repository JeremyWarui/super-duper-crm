// Signing out stops this device's call alerts: the push service then answers the server with
// "gone" and the server drops the device.
export function forgetAlerts() {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;
  navigator.serviceWorker
    .getRegistration()
    .then((reg) => reg?.pushManager.getSubscription())
    .then((sub) => sub?.unsubscribe())
    .catch(() => {});
}
