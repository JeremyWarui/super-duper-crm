// After sign-in, offers to ring this phone when the team starts a call; once dismissed it stays away.
import { useEffect, useState } from "react";
import { usePushKey } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { dismiss, dismissed, enableAlerts, needsHomeScreen, pushSupported, subscribed } from "@/lib/push";

export default function CallAlerts() {
  const key = usePushKey().data?.key;
  const [state, setState] = useState("checking");
  const [error, setError] = useState("");
  useEffect(() => {
    if (!pushSupported() || dismissed() || Notification.permission === "denied") return setState("hidden");
    subscribed().then((on) => setState(on ? "hidden" : "offer"), () => setState("hidden"));
  }, []);
  if (!key || state === "hidden" || state === "checking") return null;
  if (state === "on") return <p role="status" className="mb-4 rounded-lg bg-ok/10 px-4 py-3 text-ui font-semibold">Call alerts are on for this phone.</p>;
  const turnOn = () => {
    setState("busy");
    enableAlerts(key).then(() => setState("on"), (e) => { setError(e.message); setState("offer"); });
  };
  return (
    <div role="region" aria-label="Call alerts" className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line bg-surface px-4 py-3">
      <div className="grid gap-1">
        <span className="font-semibold">Get an alert on this phone when the team starts a call.</span>
        {needsHomeScreen() && <span className="text-small text-muted-foreground">On iPhone, first tap Share, then Add to Home Screen, and open the app from there (iOS 16.4 or later).</span>}
        {error && <span className="text-small text-bad-foreground">{error}</span>}
      </div>
      <div className="flex gap-2">
        <Button size="sm" loading={state === "busy"} disabled={state === "busy"} onClick={turnOn}>Enable call alerts</Button>
        <Button size="sm" variant="quiet" onClick={() => { dismiss(); setState("hidden"); }}>Not now</Button>
      </div>
    </div>
  );
}
