// Who a call or an announcement reaches: the whole campaign, a ward, or in an MCA race a centre.
import { useMemo } from "react";
import { useTargets } from "@/api/hooks";
import { NativeSelect } from "@/components/ui/input";
import { unitOf } from "./helpers";

/** The campaign's units from its targets, as { key, label, ward, centre }, sorted by label. */
export function useUnitOptions(campaign) {
  const targets = useTargets(campaign.id);
  const { byCentre } = unitOf(campaign);
  return useMemo(() => {
    const seen = new Map();
    for (const t of targets.data || []) {
      if (byCentre && t.registration_centre) {
        seen.set(t.registration_centre, { key: t.registration_centre, label: `${t.centre_name} centre`, ward: t.ward, centre: t.registration_centre });
      } else if (!byCentre && t.ward) {
        seen.set(t.ward, { key: t.ward, label: `${t.ward_name} ward`, ward: t.ward, centre: null });
      }
    }
    return [...seen.values()].sort((a, b) => a.label.localeCompare(b.label));
  }, [targets.data, byCentre]);
}

/** The request body's place for a picked unit key; blank is the whole campaign. */
export const placeOf = (options, key) => {
  const unit = options.find((o) => o.key === key);
  return { ward: unit?.ward ?? null, centre: unit?.centre ?? null };
};

/** A select of the campaign's units; `wholeCampaign` false makes a unit required (a coordinator). */
export function UnitSelect({ campaign, options, value, onChange, wholeCampaign = true, ...props }) {
  const { noun } = unitOf(campaign);
  return (
    <NativeSelect value={value} onChange={(e) => onChange(e.target.value)} {...props}>
      <option value="">{wholeCampaign ? "The whole campaign" : `Pick a ${noun}`}</option>
      {options.map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
    </NativeSelect>
  );
}
