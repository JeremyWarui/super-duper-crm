import { useState } from "react";
import { formatNumber as fmt, plural } from "@/lib/format";
import { useInviteToEvent } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { ErrorText } from "@/components/ui/error-text";
import { FormActions } from "@/components/ui/form-actions";
import { FilterPills } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { useAuth } from "@/store/auth";
import { composed } from "@/lib/sms";
import { MessageField } from "@/components/SmsParts";
import { SUPPORT_LEVELS } from "@/lib/labels";

// Who may really text; anyone else who changes the event can preview.
const SENDERS = ["candidate", "manager"];

// Who an invite goes to, named as groups.
const AUDIENCE = SUPPORT_LEVELS.map(([value, label]) => [value, value === "supporter" ? "Supporters" : label]);

export default function InviteForm({ event, onClose }) {
  const invite = useInviteToEvent();
  const canSend = SENDERS.includes(useAuth((s) => s.user?.role));
  const [message, setMessage] = useState(`${event.title}${event.venue ? ` at ${event.venue}` : ""}. Come through.`);
  const [levels, setLevels] = useState(["supporter", "undecided"]);
  const [wholeCampaign, setWholeCampaign] = useState(false);
  const [result, setResult] = useState(null);

  const ok = composed(message).fits && !invite.isPending;
  const toggle = (key) => setLevels((L) => (L.includes(key) ? L.filter((k) => k !== key) : [...L, key]));
  const send = (dry) =>
    invite.mutate(
      { id: event.id, message: message.trim(), support_levels: levels, whole_campaign: wholeCampaign, dry_run: dry },
      { onSuccess: setResult },
    );

  return (
    <Dialog title="Invite supporters" description={`${event.title} · ${wholeCampaign ? "whole campaign" : event.ward_name}`} onClose={onClose}>
      <MessageField value={message} onChange={(m) => { setMessage(m); setResult(null); }} text={composed(message).text} />

      <div className="flex flex-col gap-1.5">
        <span className="text-small font-semibold">Send to</span>
        <FilterPills label="Send to" options={AUDIENCE} value={levels} onChange={(key) => { toggle(key); setResult(null); }} />
      </div>
      <label className="flex min-h-11 cursor-pointer items-start gap-3 text-ui text-muted-foreground">
        <input type="checkbox" checked={wholeCampaign} onChange={(e) => { setWholeCampaign(e.target.checked); setResult(null); }} className="mt-0.5 size-[18px] flex-none accent-primary" />
        Everyone on the campaign, not just {event.ward_name}
      </label>

      {!canSend && <p className="text-small text-muted-foreground">Only the candidate or the campaign manager sends texts.</p>}
      {result && <InviteResult result={result} />}
      <ErrorText error={invite.isError && invite.error} />

      <FormActions>
        <Button shape="rounded" variant="quiet" onClick={onClose}>Close</Button>
        <Button shape="rounded" variant="quiet" onClick={() => send(true)} disabled={!ok}>{invite.isPending ? "Working…" : "Preview"}</Button>
        {canSend && <Button shape="rounded" disabled={!ok} onClick={() => send(false)}>{invite.isPending ? "Sending…" : "Send"}</Button>}
      </FormActions>
    </Dialog>
  );
}

function InviteResult({ result }) {
  const tone = result.delivered ? "ok" : "warn";
  return (
    <Card variant="tinted" className={cn("border-l-[3px]", result.delivered ? "border-l-primary" : "border-l-warn-foreground")}>
      <div className="flex items-center gap-2 font-semibold">
        {result.dry_run ? "Preview" : result.delivered ? "Sent" : "Not sent"}
        <Badge tone={tone}>{result.provider}</Badge>
      </div>
      <p className="text-small text-muted-foreground">
        {plural(result.supporters_matched, "supporter")} matched ·
        {" "}{plural(result.requested, "usable number")} ·
        {" "}{plural(result.parts, "part")} each
        {result.opted_out > 0 && <> · {fmt(result.opted_out)} opted out, left out</>}
      </p>
      {result.rejected.length > 0 && (
        <p className="text-small text-bad-foreground">
          {plural(result.rejected.length, "number")} unusable: {result.rejected.slice(0, 4).map((r) => r.phone || "(blank)").join(", ")}
        </p>
      )}
      {result.detail && <p className="text-small text-muted-foreground">{result.detail}</p>}
      {!result.dry_run && result.delivered && <p className="text-small font-semibold text-ok-foreground">Reached is now {fmt(result.number_reached)}.</p>}
    </Card>
  );
}
