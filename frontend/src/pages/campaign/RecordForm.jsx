import { useState } from "react";
import { Modal } from "../../components/ui";
import { useRecordEvent } from "../../api/hooks";
import { Btn, Label, PrimaryBtn } from "./controls";

export default function RecordForm({ event, onClose }) {
  const record = useRecordEvent();
  const [reached, setReached] = useState(""); const [attended, setAttended] = useState("");
  const r = Number(reached), a = Number(attended);
  const ok = reached !== "" && attended !== "" && r > 0 && a <= r;
  return (
    <Modal title="Record attendance" sub={`${event.title} · ${event.ward_name}`} onClose={onClose}>
      <Label>How many were reached / invited</Label><input type="number" className="app-field" value={reached} onChange={(e) => setReached(e.target.value)} />
      <div className="field-gap" /><Label>How many attended</Label><input type="number" className="app-field" value={attended} onChange={(e) => setAttended(e.target.value)} />
      {reached !== "" && attended !== "" && a > r && <div className="form-error">Attendance can't exceed those reached.</div>}
      {record.isError && <div className="form-error">{record.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Btn onClick={onClose}>Cancel</Btn>
        <PrimaryBtn disabled={!ok || record.isPending} onClick={() => record.mutate({ id: event.id, number_reached: r, number_attended: a }, { onSuccess: onClose })}>{record.isPending ? "Saving…" : "Save & mark done"}</PrimaryBtn>
      </div>
    </Modal>
  );
}

