import { useEffect, useRef, useState } from "react";
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
import { isLead } from "./helpers";
import { Check, Field, NativeSelect } from "@/components/ui/input";


// Who an invite goes to, named as groups.
const AUDIENCE = SUPPORT_LEVELS.map(([value, label]) => [value, value === "supporter" ? "Supporters" : label]);

export default function InviteForm({ event, onClose }) {
  const invite = useInviteToEvent();
  const canSend = isLead(useAuth((s) => s.user?.role));
  const [message, setMessage] = useState(`${event.title}${event.venue ? ` at ${event.venue}` : ""}. Come through.`);
  const [levels, setLevels] = useState(["supporter", "undecided"]);
  const [wholeCampaign, setWholeCampaign] = useState(false);
  const [language, setLanguage] = useState("en");
  const [result, setResult] = useState(null);

  const ok = composed(message).fits && !invite.isPending && levels.length > 0;
  const settings = { id: event.id, message: message.trim(), support_levels: levels, whole_campaign: wholeCampaign, language };
  const current = JSON.stringify(settings);
  const latest = useRef(current);
  useEffect(() => { latest.current = current; }, [current]);
  // Send shows only while the preview on screen was made for exactly these settings.
  const previewed = result?.dry_run && result.settings === current ? result : null;
  const toggle = (key) => setLevels((L) => (L.includes(key) ? L.filter((k) => k !== key) : [...L, key]));
  const send = (dry) =>
    invite.mutate({ ...settings, dry_run: dry }, { onSuccess: (r) => { if (latest.current === current) setResult({ ...r, settings: current }); } });

  return (
    <Dialog title="Invite contacts" description={`${event.title} · ${wholeCampaign ? "whole campaign" : event.ward_name}`} onClose={onClose}>
      <MessageField value={message} onChange={(m) => { setMessage(m); setResult(null); }} text={composed(message).text} />

      <div className="flex flex-col gap-1.5">
        <span className="text-small font-semibold">Send to</span>
        <FilterPills label="Send to" options={AUDIENCE} value={levels} onChange={(key) => { toggle(key); setResult(null); }} />
      </div>
      <Check className="text-ui text-muted-foreground" checked={wholeCampaign} onChange={(e) => { setWholeCampaign(e.target.checked); setResult(null); }}>
        Everyone on the campaign, not just {event.ward_name}
      </Check>

      <Field label="Language">
        <NativeSelect value={language} onChange={(e) => { setLanguage(e.target.value); setResult(null); }}>
          <option value="en">English</option>
          <option value="sw">Kiswahili</option>
        </NativeSelect>
      </Field>
      {canSend && !previewed && <p className="text-small text-muted-foreground">Preview first to see who it reaches and what it costs; Send appears after.</p>}
      <p className="text-small text-muted-foreground">The text must carry the candidate's name. It goes to contacts who agreed to be texted, in batches between 08:00 and 18:00.</p>

      {!canSend && <p className="text-small text-muted-foreground">Only the candidate or the campaign manager sends texts.</p>}
      {result && <InviteResult result={result} />}
      <ErrorText error={invite.isError && invite.error} />

      <FormActions>
        <Button variant="quiet" onClick={onClose}>Close</Button>
        <Button loading={invite.isPending} variant="quiet" onClick={() => send(true)} disabled={!ok}>{invite.isPending ? "Working…" : "Preview"}</Button>
        {canSend && previewed && previewed.requested > 0 && (
          <Button loading={invite.isPending} disabled={!ok} onClick={() => send(false)}>{invite.isPending ? "Sending…" : `Send to ${plural(previewed.requested, "person", "people")}`}</Button>
        )}
      </FormActions>
    </Dialog>
  );
}

const kes = (cents) => `KES ${(cents / 100).toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

function InviteResult({ result }) {
  const queued = !result.dry_run && result.run_status;
  const tone = result.delivered || queued ? "ok" : "warn";
  return (
    <Card variant="tinted" className={cn("border-l-[3px]", result.delivered ? "border-l-primary" : "border-l-warn-foreground")}>
      <div className="flex items-center gap-2 font-semibold">
        {result.dry_run ? "Preview" : result.run_status === "completed" ? "Sent" : queued ? "Queued" : "Not sent"}
        <Badge tone={tone}>{result.provider}</Badge>
      </div>
      <p className="text-small text-muted-foreground">
        {plural(result.supporters_matched, "contact")} matched ·
        {" "}{plural(result.requested, "usable number")} ·
        {" "}{plural(result.parts, "part")} each
        {result.opted_out > 0 && <> · {fmt(result.opted_out)} opted out, left out</>}
      </p>
      <p className="text-small font-semibold" role="status">
        {result.dry_run ? "Would cost" : "Estimated cost"} about {kes(result.estimated_cost_cents)}
      </p>
      {result.rejected.length > 0 && (
        <p className="text-small text-bad-foreground">
          {plural(result.rejected.length, "number")} unusable{result.dry_run ? "" : `: ${result.rejected.slice(0, 4).map((r) => r.phone || "(blank)").join(", ")}`}
        </p>
      )}
      {result.detail && <p className="text-small text-muted-foreground">{result.detail}</p>}
      {!result.dry_run && result.delivered && <p className="text-small font-semibold text-ok-foreground">Reached is now {fmt(result.number_reached)}.</p>}
    </Card>
  );
}
