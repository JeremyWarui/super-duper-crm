import { useState } from "react";
import { useCounties } from "@/api/hooks";
import { Field, FilterSelect, NativeSelect } from "@/components/ui/input";
import { useWardOptions } from "./helpers";

/**
 * A ward select over the campaign's targeted wards. With `perCounty` it picks the county first and
 * lists that county's wards; otherwise it lists `wardOptions`. `blank` reads the empty option.
 */
export default function WardField({ campaignId, perCounty, wardOptions, value, onChange, blank }) {
  const [county, setCounty] = useState("");
  const counties = useCounties(perCounty).data || [];
  const inCounty = useWardOptions(perCounty && county ? campaignId : undefined, { county });
  const options = perCounty ? inCounty : wardOptions;
  return (
    <>
      {perCounty && (
        <FilterSelect labelled label="County" blank="Pick the county" value={county} options={counties} onChange={(id) => { setCounty(id); onChange(""); }} />
      )}
      <Field label="Ward">
        <NativeSelect aria-label="Ward" value={value} disabled={perCounty && !county} onChange={(e) => onChange(e.target.value)}>
          {(blank || perCounty) && <option value="">{blank || "Pick the ward"}</option>}
          {options.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
        </NativeSelect>
      </Field>
    </>
  );
}
