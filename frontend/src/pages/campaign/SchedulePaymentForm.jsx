import { useState } from "react";
import { Modal } from "../../components/ui";
import { useEvents, useMobilizers, useSchedulePayment } from "../../api/hooks";
import { Btn, Label, PrimaryBtn } from "./controls";

export default function SchedulePaymentForm({ campaignId, onClose }) {
  const schedule = useSchedulePayment();
  const events = (useEvents(campaignId).data || []).filter((e) => e.status !== "cancelled");
  const mobilizers = useMobilizers(campaignId).data || [];
  const [eventId, setEventId] = useState("");
  const [picked, setPicked] = useState(null);  // null until the mobilizer box is changed
  const [amount, setAmount] = useState("");
  const event = events.find((e) => e.id === eventId);
  const mobilizer = picked ?? event?.mobilizer ?? "";
  const ok = event && mobilizer && Number.isInteger(Number(amount)) && Number(amount) > 0;
  const save = () => schedule.mutate({ campaign: campaignId, event: eventId, mobilizer, amount_kes: Number(amount) }, { onSuccess: onClose });
  return (
    <Modal title="Schedule payment" sub="Paid per event, to the mobilizer who ran it." onClose={onClose}>
      <Label>Event</Label>
      <select aria-label="Event" className="app-field" value={eventId} onChange={(e) => { setEventId(e.target.value); setPicked(null); }}>
        <option value="">Pick an event</option>
        {events.map((e) => <option key={e.id} value={e.id}>{e.title || e.ward_name}</option>)}
      </select>
      <div className="field-gap" /><Label>Mobilizer</Label>
      <select aria-label="Mobilizer" className="app-field" value={mobilizer} onChange={(e) => setPicked(e.target.value)}>
        <option value="">Pick a mobilizer</option>
        {mobilizers.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}
      </select>
      <div className="field-gap" /><Label>Amount (KES)</Label>
      <input aria-label="Amount" type="number" min={1} step={1} className="app-field" value={amount} onChange={(e) => setAmount(e.target.value)} />
      {schedule.error && <div className="form-error">{schedule.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Btn onClick={onClose}>Cancel</Btn>
        <PrimaryBtn disabled={!ok || schedule.isPending} onClick={save}>{schedule.isPending ? "Saving…" : "Schedule"}</PrimaryBtn>
      </div>
    </Modal>
  );
}

