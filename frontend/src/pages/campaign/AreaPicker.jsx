import { useState } from "react";
import { FormActions, Modal } from "../../components/ui";
import { useArea, useSetArea } from "../../api/hooks";
import { Btn, ErrorMsg, Loading, PrimaryBtn } from "./controls";
import { useUnits } from "./helpers";

// Picks a coordinator's area from the campaign's targeted units: wards, or centres in an MCA race.
export default function AreaPicker({ campaign, person, onClose }) {
  const byCentre = campaign.operational_grain === "centre";
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
    <Modal title={`Area for ${person.full_name || person.username}`} sub={`The ${noun} this coordinator works. They see nothing outside them.`} onClose={onClose}>
      {area.isLoading || picked === null ? (area.error ? <ErrorMsg error={area.error} /> : <Loading />) : (
        <div className="release-list">
          {options.map((o) => (
            <label key={o.id} className="flex items-center gap-2 checkbox-row">
              <input type="checkbox" className="checkbox" checked={picked.has(o.id)} onChange={() => toggle(o.id)} />{o.name}
            </label>
          ))}
          {options.length === 0 && <div className="muted">This campaign has no targeted {noun} yet. Set targets first.</div>}
        </div>
      )}
      {save.error && <div className="form-error">{save.error.message}</div>}
      <FormActions>
        <Btn onClick={onClose}>Cancel</Btn>
        <PrimaryBtn disabled={picked === null || save.isPending} onClick={submit}>{save.isPending ? "Saving…" : `Save ${picked?.size ?? 0} ${noun}`}</PrimaryBtn>
      </FormActions>
    </Modal>
  );
}
