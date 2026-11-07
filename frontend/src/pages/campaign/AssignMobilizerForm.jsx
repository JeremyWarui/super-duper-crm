import { useState } from "react";
import { useUpdateMobilizer } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ErrorText } from "@/components/ui/error-text";
import { FormActions } from "@/components/ui/form-actions";
import { Field, NativeSelect } from "@/components/ui/input";

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
    <Dialog title={`Mobilizer for ${unit.unit}`} description={holder ? `Now: ${holder.full_name}` : `Pick a mobilizer without a ${unitWord}.`} onClose={onClose}>
      {free.length > 0 ? (
        <Field label="Mobilizer">
          <NativeSelect aria-label="Mobilizer" value={chosen} onChange={(e) => setPicked(e.target.value)}>
            {free.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}
          </NativeSelect>
        </Field>
      ) : (
        <p className="text-muted-foreground">Every mobilizer already has a {unitWord}. Add one on the Mobilizers page.</p>
      )}
      <ErrorText error={update.error} />
      <FormActions>
        {holder && <Button shape="rounded" variant="quiet" onClick={remove} disabled={update.isPending}>Remove {holder.full_name}</Button>}
        <Button shape="rounded" variant="quiet" onClick={onClose}>Cancel</Button>
        <Button shape="rounded" disabled={!chosen || update.isPending} onClick={assign}>{update.isPending ? "Saving…" : "Assign"}</Button>
      </FormActions>
    </Dialog>
  );
}
