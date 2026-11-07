import { useState } from "react";
import { formatNumber as fmt, plural } from "../../lib/format";
import { Badge, Chip, FormActions, Modal } from "../../components/ui";
import { useInviteToEvent } from "../../api/hooks";
import { useAuth } from "../../store/auth";
import { FOOTER, partsOf } from "../../lib/sms";
import { Btn, Label, PrimaryBtn } from "./controls";

const LEVELS = [["supporter", "Supporters"], ["undecided", "Undecided"], ["opposed", "Opposed"]];
// Who may really text; anyone else who changes the event can preview.
const SENDERS = ["candidate", "manager"];

export default function InviteForm({ event, onClose }) {
  const invite = useInviteToEvent();
  const canSend = SENDERS.includes(useAuth((s) => s.user?.role));
  const [message, setMessage] = useState(`${event.title}${event.venue ? ` at ${event.venue}` : ""}. Come through.`);
  const [levels, setLevels] = useState(["supporter", "undecided"]);
  const [wholeCampaign, setWholeCampaign] = useState(false);
  const [result, setResult] = useState(null);

  const text = message.trim() + FOOTER;
  const parts = partsOf(text);
  const ok = message.trim().length > 0 && !invite.isPending;
  const toggle = (key) => setLevels((L) => (L.includes(key) ? L.filter((k) => k !== key) : [...L, key]));
  const send = (dry) =>
    invite.mutate(
      { id: event.id, message: message.trim(), support_levels: levels, whole_campaign: wholeCampaign, dry_run: dry },
      { onSuccess: setResult },
    );

  return (
    <Modal title="Invite supporters" sub={`${event.title} · ${wholeCampaign ? "whole campaign" : event.ward_name}`} onClose={onClose}>
      <Label>Message</Label>
      <textarea className="textarea app-field" maxLength={895} value={message} onChange={(e) => { setMessage(e.target.value); setResult(null); }} />
      <div className="field-hint">{text.length} characters · {plural(parts, "SMS part")} per person · "Reply STOP to opt out" is added</div>

      <div className="field-gap" /><Label>Send to</Label>
      <div className="flex flex-wrap gap-1 chip-row">
        {LEVELS.map(([key, label]) => (
          <Chip key={key} on={levels.includes(key)} onClick={() => { toggle(key); setResult(null); }}>{label}</Chip>
        ))}
      </div>
      <label className="flex items-start gap-2 checkbox-row">
        <input type="checkbox" checked={wholeCampaign} onChange={(e) => { setWholeCampaign(e.target.checked); setResult(null); }} className="checkbox" />
        Everyone on the campaign, not just {event.ward_name}
      </label>

      {!canSend && <div className="field-hint">Only the candidate or the campaign manager sends texts.</div>}
      {result && <InviteResult result={result} />}
      {invite.isError && <div className="form-error">{invite.error.message}</div>}

      <FormActions>
        <Btn onClick={onClose}>Close</Btn>
        <Btn onClick={() => send(true)} disabled={!ok}>{invite.isPending ? "Working…" : "Preview"}</Btn>
        {canSend && <PrimaryBtn disabled={!ok} onClick={() => send(false)}>{invite.isPending ? "Sending…" : "Send"}</PrimaryBtn>}
      </FormActions>
    </Modal>
  );
}

function InviteResult({ result }) {
  const tone = result.delivered ? "good" : "warn";
  return (
    <div className={`result tone-${tone}`}>
      <div className="result-title">
        {result.dry_run ? "Preview" : result.delivered ? "Sent" : "Not sent"}
        <span className="inline-badge"><Badge text={result.provider} tone={tone} /></span>
      </div>
      <div className="result-text">
        {plural(result.supporters_matched, "supporter")} matched ·
        {" "}{plural(result.requested, "usable number")} ·
        {" "}{plural(result.parts, "part")} each
        {result.opted_out > 0 && <> · {fmt(result.opted_out)} opted out, left out</>}
      </div>
      {result.rejected.length > 0 && (
        <div className="result-bad">
          {plural(result.rejected.length, "number")} unusable: {result.rejected.slice(0, 4).map((r) => r.phone || "(blank)").join(", ")}
        </div>
      )}
      {result.detail && <div className="result-note">{result.detail}</div>}
      {!result.dry_run && result.delivered && <div className="result-good">Reached is now {fmt(result.number_reached)}.</div>}
    </div>
  );
}

