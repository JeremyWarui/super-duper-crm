import { useState } from "react";
import { Modal } from "../../components/ui";
import { useAssignments, usePayments, useSchedulePayment } from "../../api/hooks";
import { Btn, Label, PrimaryBtn } from "./controls";
import { kes } from "./helpers";

const APPROVER = { coordinator: "the campaign manager", manager: "the candidate" };

// Pays one done assignment, for its amount, to its mobilizer or agent.
export default function SchedulePaymentForm({ campaignId, role, onClose }) {
  const schedule = useSchedulePayment();
  const done = useAssignments(campaignId, "done").data || [];
  const paid = new Set((usePayments(campaignId).data || []).filter((p) => p.status !== "cancelled").map((p) => p.assignment));
  const open = done.filter((a) => !paid.has(a.id));
  const [picked, setPicked] = useState("");
  const work = open.find((a) => a.id === picked);
  const then = APPROVER[role] ? ` It then waits for ${APPROVER[role]} to approve it.` : "";
  return (
    <Modal title="Schedule payment" sub={`For work marked done.${then}`} onClose={onClose}>
      <Label>Work done</Label>
      <select aria-label="Work done" className="app-field" value={picked} onChange={(e) => setPicked(e.target.value)}>
        <option value="">{open.length ? "Pick the work" : "No done work waits for payment"}</option>
        {open.map((a) => <option key={a.id} value={a.id}>{a.label} · {a.member_name} · {kes(a.amount_kes)}</option>)}
      </select>
      {work && <div className="page-note">{kes(work.amount_kes)} to {work.member_name}.</div>}
      {schedule.error && <div className="form-error">{schedule.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Btn onClick={onClose}>Cancel</Btn>
        <PrimaryBtn disabled={!work || schedule.isPending} onClick={() => schedule.mutate({ assignment: work.id }, { onSuccess: onClose })}>{schedule.isPending ? "Saving…" : "Schedule"}</PrimaryBtn>
      </div>
    </Modal>
  );
}
