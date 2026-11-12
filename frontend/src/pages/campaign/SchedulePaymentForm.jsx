import { useState } from "react";
import { useAssignments, usePayments, useSchedulePayment } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ErrorText } from "@/components/ui/error-text";
import { FormActions } from "@/components/ui/form-actions";
import { Field, NativeSelect } from "@/components/ui/input";
import { formatKES } from "@/lib/format";

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
    <Dialog title="Schedule payment" description={`For work marked done.${then}`} onClose={onClose}>
      <Field label="Work done">
        <NativeSelect aria-label="Work done" value={picked} onChange={(e) => setPicked(e.target.value)}>
          <option value="">{open.length ? "Pick the work" : "No done work waits for payment"}</option>
          {open.map((a) => <option key={a.id} value={a.id}>{a.label} · {a.member_name} · {formatKES(a.amount_kes)}</option>)}
        </NativeSelect>
      </Field>
      {work && <p className="text-small text-muted-foreground">{formatKES(work.amount_kes)} to {work.member_name}.</p>}
      <ErrorText error={schedule.error} />
      <FormActions>
        <Button variant="quiet" onClick={onClose}>Cancel</Button>
        <Button disabled={!work || schedule.isPending} onClick={() => schedule.mutate({ assignment: work.id }, { onSuccess: onClose })}>{schedule.isPending ? "Saving…" : "Schedule"}</Button>
      </FormActions>
    </Dialog>
  );
}
