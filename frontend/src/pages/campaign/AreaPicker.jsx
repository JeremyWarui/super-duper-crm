import { useState } from "react";
import { useArea, useConstituencies, useCounties, useSetArea } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ErrorText } from "@/components/ui/error-text";
import { FormActions } from "@/components/ui/form-actions";
import { LoadingText } from "@/components/ui/loading-text";
import { isNational, unitOf, useUnits } from "./helpers";
import { displayName } from "@/lib/format";
import { Check } from "@/components/ui/input";

const KEYS = ["counties", "constituencies", "wards", "registration_centres"];

function Ticks({ heading, options, picked, onToggle }) {
  if (!options.length) return null;
  return (
    <div className="flex flex-col">
      {heading && <span className="mt-2 text-small font-semibold text-muted-foreground">{heading}</span>}
      {options.map((o) => (
        <Check key={o.id} className="items-center" checked={picked.has(o.id)} onChange={() => onToggle(o.id)}>{o.name}</Check>
      ))}
    </div>
  );
}

// A national seat's counties, each opening to its constituencies.
function CountyTicks({ picked, onToggle }) {
  const counties = useCounties().data || [];
  const [open, setOpen] = useState("");
  const constituencies = useConstituencies(open).data || [];
  return (
    <div className="flex flex-col">
      {counties.map((c) => (
        <div key={c.id} className="flex flex-col">
          <div className="flex items-center justify-between gap-2">
            <Check className="items-center" checked={picked.counties.has(c.id)} onChange={() => onToggle("counties", c.id)}>{c.name}</Check>
            <Button variant="quiet" size="sm" aria-expanded={open === c.id} onClick={() => setOpen(open === c.id ? "" : c.id)}>
              {open === c.id ? "Hide constituencies" : "Constituencies"}
            </Button>
          </div>
          {open === c.id && (
            <div className="pl-7">
              <Ticks options={constituencies} picked={picked.constituencies} onToggle={(id) => onToggle("constituencies", id)} />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/**
 * Picks a coordinator's area: counties or their constituencies for a national seat; constituencies
 * and wards for a county seat; wards, or centres in an MCA race, below that.
 */
export default function AreaPicker({ campaign, person, onClose }) {
  const { byCentre } = unitOf(campaign);
  const national = isNational(campaign);
  const units = useUnits(national ? undefined : campaign.id);
  const constituencies = useConstituencies(campaign.office_level === "county" ? campaign.county : undefined).data || [];
  const area = useArea(campaign.id, person.id);
  const save = useSetArea();
  const [chosen, setChosen] = useState(null);
  const saved = area.data ? Object.fromEntries(KEYS.map((k) => [k, new Set(area.data[k] || [])])) : null;
  const picked = chosen ?? saved;

  const unitKey = byCentre ? "registration_centres" : "wards";
  const options = [...new Map(units.map((u) => [byCentre ? u.registration_centre : u.ward, u.name])).entries()]
    .filter(([id]) => id).map(([id, name]) => ({ id, name }));
  const toggle = (key, id) => {
    const next = new Set(picked[key]);
    if (next.has(id)) next.delete(id); else next.add(id);
    setChosen({ ...picked, [key]: next });
  };
  const submit = () => {
    const body = Object.fromEntries(KEYS.map((k) => [k, [...picked[k]]]));
    save.mutate({ campaign: campaign.id, user: person.id, ...body }, { onSuccess: onClose });
  };
  const count = picked ? KEYS.reduce((n, k) => n + picked[k].size, 0) : 0;
  const unitWord = byCentre ? "centres" : "wards";
  const saveWord = national || constituencies.length ? (count === 1 ? "place" : "places") : unitWord;
  const noun = national ? "counties or constituencies" : byCentre ? "centres" : constituencies.length ? "constituencies or wards" : "wards";

  return (
    <Dialog title={`Area for ${displayName(person)}`} description={`The ${noun} this coordinator works. They see nothing outside them.`} onClose={onClose}>
      {area.isLoading || picked === null ? (area.error ? <ErrorText error={area.error} /> : <LoadingText />) : (
        <div className="flex flex-col">
          {national ? <CountyTicks picked={picked} onToggle={toggle} /> : (
            <>
              <Ticks heading="Whole constituencies" options={constituencies} picked={picked.constituencies} onToggle={(id) => toggle("constituencies", id)} />
              <Ticks heading={constituencies.length ? "Wards" : null} options={options} picked={picked[unitKey]} onToggle={(id) => toggle(unitKey, id)} />
              {options.length === 0 && <p className="text-muted-foreground">This campaign has no targeted {unitWord} yet. Set targets first.</p>}
            </>
          )}
        </div>
      )}
      <ErrorText error={save.error} />
      <FormActions>
        <Button variant="quiet" onClick={onClose}>Cancel</Button>
        <Button loading={save.isPending} disabled={picked === null || save.isPending} onClick={submit}>{save.isPending ? "Saving…" : `Save ${count} ${saveWord}`}</Button>
      </FormActions>
    </Dialog>
  );
}
