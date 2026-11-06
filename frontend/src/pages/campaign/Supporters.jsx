import { useState } from "react";
import { useCentres, usePlaceSupporter, useSupporters, useTargets } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { FilterPills } from "@/components/ui/tabs";
import { formatNumber as fmt } from "@/lib/format";
import WsHeader, { KitError, KitLoading } from "./WsHeader";

const LEVELS = { All: null, Supporter: "supporter", Undecided: "undecided", Opposed: "opposed" };
const TONE = { supporter: "ok", undecided: "warn", opposed: "bad" };

function Summary({ all }) {
  const count = (level) => all.filter((s) => s.support_level === level).length;
  const tiles = [["On the register", all.length], ["Supporters", count("supporter")], ["Undecided", count("undecided")], ["Consent missing", all.filter((s) => !s.consent_given).length]];
  return (
    <section aria-label="Summary" className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-4">
      {tiles.map(([label, value]) => (
        <Card key={label} variant="tile">
          <span className="text-ui text-muted-foreground">{label}</span>
          <span className="font-display text-[28px] leading-tight font-extrabold tabular-nums">{fmt(value)}</span>
        </Card>
      ))}
    </section>
  );
}

// The supporter register, private to the campaign team; in an MCA race each one sits at a centre.
export default function Supporters({ campaign, mine, onModal }) {
  const centreWard = campaign.operational_grain === "centre" ? campaign.ward : null;
  const { data, isLoading, error } = useSupporters(campaign.id);
  const targetsQuery = useTargets(campaign.id);
  const targeted = new Set((targetsQuery.data || []).map((t) => t.registration_centre));
  const showCentre = centreWard && targetsQuery.isSuccess;
  const allCentres = useCentres(centreWard).data || [];
  const centres = allCentres.filter((c) => targeted.has(c.id));
  const centreName = (id) => allCentres.find((c) => c.id === id)?.name;
  const place = usePlaceSupporter();
  const [filter, setFilter] = useState("All");
  const all = data || [];
  const shown = LEVELS[filter] ? all.filter((s) => s.support_level === LEVELS[filter]) : all;
  const action = mine ? null : <Button shape="rounded" onClick={() => onModal({ type: "link" })}>Sign-up link</Button>;
  return (
    <>
      <WsHeader context={mine ? "My work" : "Field"} title={mine ? "My supporters" : "Supporters"} sub="Private to your campaign team. Never shared with the party." actions={action} />
      {isLoading && <KitLoading />}
      {error && <KitError error={error} />}
      {data && (
        <>
          <Summary all={all} />
          <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Supporter list">
            <FilterPills label="Support" options={Object.keys(LEVELS)} value={filter} onChange={setFilter} />
            <Table stack minWidth={560}>
              <THead><TR><TH>Name</TH><TH>Phone</TH><TH>Support</TH>{showCentre && <TH>Centre</TH>}<TH>Consent</TH></TR></THead>
              <TBody>
                {shown.map((s) => (
                  <TR key={s.id}>
                    <TD className="font-semibold">{s.full_name}</TD>
                    <TD className="text-muted-foreground tabular-nums">{s.phone}</TD>
                    <TD><Badge tone={TONE[s.support_level]} className="capitalize">{s.support_level}</Badge></TD>
                    {showCentre && (
                      <TD>{targeted.has(s.registration_centre) ? centreName(s.registration_centre) || "Unknown centre" : (
                        <select aria-label={`Centre for ${s.full_name}`} value="" disabled={place.isPending} onChange={(e) => place.mutate({ id: s.id, registration_centre: e.target.value })}
                          className="h-10 max-w-full rounded-[10px] border-[1.5px] border-line-control bg-white px-2.5 text-ui max-sm:h-11">
                          <option value="">{s.registration_centre ? `${centreName(s.registration_centre) || "Centre"} has no target` : "Needs a centre"}</option>
                          {centres.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                        </select>
                      )}</TD>
                    )}
                    <TD>{s.consent_given ? <Badge tone="ok">Given</Badge> : <Badge tone="bad">Missing</Badge>}</TD>
                  </TR>
                ))}
                {shown.length === 0 && <TR><TD colSpan={5} className="text-muted-foreground">None yet.</TD></TR>}
              </TBody>
            </Table>
            {place.isError && <p role="alert" className="font-semibold text-destructive">{place.error.message}</p>}
          </Card>
        </>
      )}
    </>
  );
}
