import { useState } from "react";
import { Modal } from "../../components/ui";
import { useUpdateMobilizer } from "../../api/hooks";
import { Btn, Label, PrimaryBtn } from "./controls";

// Puts an unassigned mobilizer on the clicked unit; the unit comes from the row.
export default function AssignMobilizerForm({ unit, holder, mobilizers, onClose }) {
  const update = useUpdateMobilizer();
  const free = mobilizers.filter((m) => !m.ward);
  const unitWord = unit.registration_centre ? "centre" : "ward";
  const [picked, setPicked] = useState("");
  const chosen = picked || free[0]?.id || "";
  const assign = () => update.mutate({ id: chosen, ward: unit.ward, registration_centre: unit.registration_centre ?? null }, { onSuccess: onClose });
  const remove = () => update.mutate({ id: holder.id, ward: null, registration_centre: null }, { onSuccess: onClose });

  return (
    <Modal title={`Mobilizer for ${unit.unit}`} sub={holder ? `Now: ${holder.full_name}` : `Pick a mobilizer without a ${unitWord}.`} onClose={onClose}>
      {free.length > 0 ? (
        <>
          <Label>Mobilizer</Label>
          <select aria-label="Mobilizer" className="app-field" value={chosen} onChange={(e) => setPicked(e.target.value)}>
            {free.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}
          </select>
        </>
      ) : (
        <div className="muted">Every mobilizer already has a {unitWord}. Add one on the Mobilizers page.</div>
      )}
      {update.error && <div className="form-error">{update.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        {holder && <Btn onClick={remove} disabled={update.isPending}>Remove {holder.full_name}</Btn>}
        <Btn onClick={onClose}>Cancel</Btn>
        <PrimaryBtn disabled={!chosen || update.isPending} onClick={assign}>{update.isPending ? "Saving…" : "Assign"}</PrimaryBtn>
      </div>
    </Modal>
  );
}

