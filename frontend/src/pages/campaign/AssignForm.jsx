import { useState } from "react";
import { Modal } from "../../components/ui";
import { useAgents, useCreateAssignment, useMobilizers } from "../../api/hooks";
import { Btn, Label, PrimaryBtn } from "./controls";
import { useWardOptions } from "./helpers";

const KINDS = [["activity", "Activity (training or other)"], ["ward_work", "Ward work"]];

/**
 * Gives a mobilizer or agent paid work. From an event card the event is fixed; from a mobilizer
 * or agent row the person is fixed.
 */
export default function AssignForm({ campaignId, event, member, onClose }) {
  const create = useCreateAssignment();
  const mobilizers = useMobilizers(campaignId).data || [];
  const agents = useAgents(campaignId).data || [];
  const wards = useWardOptions(campaignId);
  const [kind, setKind] = useState(event ? "event" : "activity");
  const [who, setWho] = useState(member ? `${member.role}:${member.id}` : "");
  const [ward, setWard] = useState("");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [role, id] = who.split(":");
  const ok = role && id && Number.isInteger(Number(amount)) && Number(amount) > 0
    && (kind !== "ward_work" || ward) && (kind !== "activity" || description.trim());
  const save = () => create.mutate({
    campaign: campaignId,
    [role]: id,
    kind,
    event: kind === "event" ? event.id : null,
    ward: kind === "ward_work" ? ward : null,
    description: description.trim(),
    amount_kes: Number(amount),
  }, { onSuccess: onClose });
  return (
    <Modal title="Assign work" sub={event ? event.title : "It is paid once it is marked done."} onClose={onClose}>
      {!event && (
        <>
          <Label>Kind</Label>
          <select aria-label="Kind" className="app-field" value={kind} onChange={(e) => setKind(e.target.value)}>
            {KINDS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <div className="field-gap" />
        </>
      )}
      {!member && (
        <>
          <Label>Who</Label>
          <select aria-label="Who" className="app-field" value={who} onChange={(e) => setWho(e.target.value)}>
            <option value="">Pick a mobilizer or agent</option>
            <optgroup label="Mobilizers">{mobilizers.map((m) => <option key={m.id} value={`mobilizer:${m.id}`}>{m.full_name}</option>)}</optgroup>
            <optgroup label="Agents">{agents.map((a) => <option key={a.id} value={`agent:${a.id}`}>{a.full_name}</option>)}</optgroup>
          </select>
          <div className="field-gap" />
        </>
      )}
      {kind === "ward_work" && (
        <>
          <Label>Ward</Label>
          <select aria-label="Ward" className="app-field" value={ward} onChange={(e) => setWard(e.target.value)}>
            <option value="">Pick a ward</option>
            {wards.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </select>
          <div className="field-gap" />
        </>
      )}
      {kind === "activity" && (
        <>
          <Label>What</Label>
          <input aria-label="What" className="app-field" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Agent training at the ward office" />
          <div className="field-gap" />
        </>
      )}
      <Label>Amount (KES)</Label>
      <input aria-label="Amount" type="number" min={1} step={1} className="app-field" value={amount} onChange={(e) => setAmount(e.target.value)} />
      {create.error && <div className="form-error">{create.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Btn onClick={onClose}>Cancel</Btn>
        <PrimaryBtn disabled={!ok || create.isPending} onClick={save}>{create.isPending ? "Saving…" : "Assign"}</PrimaryBtn>
      </div>
    </Modal>
  );
}
