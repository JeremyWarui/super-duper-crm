import { useState } from "react";
import { useRecordEvent } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ErrorText } from "@/components/ui/error-text";
import { FormActions } from "@/components/ui/form-actions";
import { Field, Input } from "@/components/ui/input";
import { TOO_MANY_ATTENDED, attendanceOk } from "./helpers";

export default function RecordForm({ event, onClose }) {
  const record = useRecordEvent();
  const [reached, setReached] = useState(""); const [attended, setAttended] = useState("");
  const r = Number(reached), a = Number(attended);
  const ok = reached !== "" && attended !== "" && attendanceOk(r, a);
  return (
    <Dialog title="Record attendance" description={`${event.title} · ${event.ward_name}`} onClose={onClose}>
      <Field label="How many were reached / invited"><Input type="number" value={reached} onChange={(e) => setReached(e.target.value)} /></Field>
      <Field label="How many attended"><Input type="number" value={attended} onChange={(e) => setAttended(e.target.value)} /></Field>
      {reached !== "" && attended !== "" && a > r && <ErrorText error={TOO_MANY_ATTENDED} />}
      <ErrorText error={record.isError && record.error} />
      <FormActions>
        <Button shape="rounded" variant="quiet" onClick={onClose}>Cancel</Button>
        <Button shape="rounded" disabled={!ok || record.isPending} onClick={() => record.mutate({ id: event.id, number_reached: r, number_attended: a }, { onSuccess: onClose })}>{record.isPending ? "Saving…" : "Save & mark done"}</Button>
      </FormActions>
    </Dialog>
  );
}
