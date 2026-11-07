import { useState } from "react";
import { useAgents, useCreateAssignment, useMobilizers } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ErrorText } from "@/components/ui/error-text";
import { FormActions } from "@/components/ui/form-actions";
import { Field, Input, NativeSelect } from "@/components/ui/input";
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
    <Dialog title="Assign work" description={event ? event.title : "It is paid once it is marked done."} onClose={onClose}>
      {!event && (
        <Field label="Kind">
          <NativeSelect aria-label="Kind" value={kind} onChange={(e) => setKind(e.target.value)}>
            {KINDS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </NativeSelect>
        </Field>
      )}
      {!member && (
        <Field label="Who">
          <NativeSelect aria-label="Who" value={who} onChange={(e) => setWho(e.target.value)}>
            <option value="">Pick a mobilizer or agent</option>
            <optgroup label="Mobilizers">{mobilizers.map((m) => <option key={m.id} value={`mobilizer:${m.id}`}>{m.full_name}</option>)}</optgroup>
            <optgroup label="Agents">{agents.map((a) => <option key={a.id} value={`agent:${a.id}`}>{a.full_name}</option>)}</optgroup>
          </NativeSelect>
        </Field>
      )}
      {kind === "ward_work" && (
        <Field label="Ward">
          <NativeSelect aria-label="Ward" value={ward} onChange={(e) => setWard(e.target.value)}>
            <option value="">Pick a ward</option>
            {wards.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </NativeSelect>
        </Field>
      )}
      {kind === "activity" && (
        <Field label="What">
          <Input aria-label="What" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Agent training at the ward office" />
        </Field>
      )}
      <Field label="Amount (KES)">
        <Input aria-label="Amount" type="number" min={1} step={1} value={amount} onChange={(e) => setAmount(e.target.value)} />
      </Field>
      <ErrorText error={create.error} />
      <FormActions>
        <Button shape="rounded" variant="quiet" onClick={onClose}>Cancel</Button>
        <Button shape="rounded" disabled={!ok || create.isPending} onClick={save}>{create.isPending ? "Saving…" : "Assign"}</Button>
      </FormActions>
    </Dialog>
  );
}
