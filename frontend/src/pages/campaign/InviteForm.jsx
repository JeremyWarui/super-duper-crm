import { useState } from "react";
import { formatNumber as fmt } from "../../lib/format";
import { Badge, Chip, Modal } from "../../components/ui";
import { useInviteToEvent } from "../../api/hooks";
import { Btn, Label, PrimaryBtn } from "./controls";

const LEVELS = [["supporter", "Supporters"], ["undecided", "Undecided"], ["opposed", "Opposed"]];
const SMS_PART = 160;

export default function InviteForm({ event, onClose }) {
  const invite = useInviteToEvent();
  const [message, setMessage] = useState(`${event.title}${event.venue ? ` at ${event.venue}` : ""}. Come through.`);
  const [levels, setLevels] = useState(["supporter", "undecided"]);
  const [wholeCampaign, setWholeCampaign] = useState(false);
  const [result, setResult] = useState(null);

  const parts = message.length === 0 ? 0 : Math.floor((message.length - 1) / SMS_PART) + 1;
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
      <textarea className="textarea app-field" value={message} onChange={(e) => { setMessage(e.target.value); setResult(null); }} />
      <div className="field-hint">{message.length} characters · {parts} SMS part{parts === 1 ? "" : "s"} per person</div>

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

      {result && <InviteResult result={result} />}
      {invite.isError && <div className="form-error">{invite.error.message}</div>}

      <div className="flex justify-end gap-2 form-actions">
        <Btn onClick={onClose}>Close</Btn>
        <Btn onClick={() => send(true)} disabled={!ok}>{invite.isPending ? "Working…" : "Preview"}</Btn>
        <PrimaryBtn disabled={!ok} onClick={() => send(false)}>{invite.isPending ? "Sending…" : "Send"}</PrimaryBtn>
      </div>
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
        {fmt(result.supporters_matched)} supporter{result.supporters_matched === 1 ? "" : "s"} matched ·
        {" "}{fmt(result.requested)} usable number{result.requested === 1 ? "" : "s"} ·
        {" "}{result.parts} part{result.parts === 1 ? "" : "s"} each
      </div>
      {result.rejected.length > 0 && (
        <div className="result-bad">
          {result.rejected.length} number{result.rejected.length === 1 ? "" : "s"} unusable: {result.rejected.slice(0, 4).map((r) => r.phone || "(blank)").join(", ")}
        </div>
      )}
      {result.detail && <div className="result-note">{result.detail}</div>}
      {!result.dry_run && result.delivered && <div className="result-good">Reached is now {fmt(result.number_reached)}.</div>}
    </div>
  );
}

