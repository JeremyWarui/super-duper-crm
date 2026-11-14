import { useState } from "react";
import { useArea, useSetArea } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ErrorText } from "@/components/ui/error-text";
import { FormActions } from "@/components/ui/form-actions";
import { LoadingText } from "@/components/ui/loading-text";
import { unitOf, useUnits } from "./helpers";
import { displayName } from "@/lib/format";
import { Check } from "@/components/ui/input";

// Picks a coordinator's area from the campaign's targeted units: wards, or centres in an MCA race.
export default function AreaPicker({ campaign, person, onClose }) {
  const { byCentre } = unitOf(campaign);
  const units = useUnits(campaign.id);
  const area = useArea(campaign.id, person.id);
  const save = useSetArea();
  const [chosen, setPicked] = useState(null);
  const saved = area.data ? new Set(byCentre ? area.data.registration_centres : area.data.wards) : null;
  const picked = chosen ?? saved;

  const options = [...new Map(units.map((u) => [byCentre ? u.registration_centre : u.ward, u.name])).entries()]
    .filter(([id]) => id).map(([id, name]) => ({ id, name }));
  const toggle = (id) => {
    const next = new Set(picked);
    if (next.has(id)) next.delete(id); else next.add(id);
    setPicked(next);
  };
  const submit = () => {
    const ids = [...picked];
    save.mutate({ campaign: campaign.id, user: person.id, wards: byCentre ? [] : ids, registration_centres: byCentre ? ids : [] }, { onSuccess: onClose });
  };
  const noun = byCentre ? "centres" : "wards";

  return (
    <Dialog title={`Area for ${displayName(person)}`} description={`The ${noun} this coordinator works. They see nothing outside them.`} onClose={onClose}>
      {area.isLoading || picked === null ? (area.error ? <ErrorText error={area.error} /> : <LoadingText />) : (
        <div className="flex flex-col">
          {options.map((o) => (
            <Check key={o.id} className="items-center" checked={picked.has(o.id)} onChange={() => toggle(o.id)}>{o.name}
            </Check>
          ))}
          {options.length === 0 && <p className="text-muted-foreground">This campaign has no targeted {noun} yet. Set targets first.</p>}
        </div>
      )}
      <ErrorText error={save.error} />
      <FormActions>
        <Button variant="quiet" onClick={onClose}>Cancel</Button>
        <Button loading={save.isPending} disabled={picked === null || save.isPending} onClick={submit}>{save.isPending ? "Saving…" : `Save ${picked?.size ?? 0} ${noun}`}</Button>
      </FormActions>
    </Dialog>
  );
}
