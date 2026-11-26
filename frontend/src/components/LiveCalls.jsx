// A bar on every workspace page for each live call this login is invited to, with its Join button.
import { Link } from "react-router-dom";
import { useLiveCalls } from "@/api/hooks";
import { Button } from "@/components/ui/button";

export default function LiveCalls({ campaign }) {
  const calls = useLiveCalls(campaign.id).data || [];
  return calls.map((call) => (
    <div key={call.id} role="region" aria-label="Live call" className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-ok/40 bg-ok/10 px-4 py-3">
      <span className="flex items-center gap-2 font-semibold">
        <span aria-hidden className="h-2.5 w-2.5 animate-pulse rounded-full bg-ok" />
        Live {call.mode === "audio" ? "audio call" : "video call"}: {call.title}
      </span>
      <Button size="sm" asChild>
        <Link to={`/meet/${call.id}`}>Join</Link>
      </Button>
    </div>
  ));
}
