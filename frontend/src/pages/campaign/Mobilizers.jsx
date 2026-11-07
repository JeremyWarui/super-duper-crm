import { useMobilizers } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { holderOf, useUnits } from "./helpers";
import WsHeader, { KitError, KitLoading } from "./WsHeader";
import { initials } from "@/lib/format";

// How many targeted units have a mobilizer, naming the ones that have none.
function Coverage({ units, mobilizers, noun }) {
  const vacant = units.filter((u) => !holderOf(mobilizers, u));
  return (
    <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Coverage">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-card-title font-bold">Coverage</h2>
        <span className="text-ui text-muted-foreground">{units.length - vacant.length} of {units.length} {noun}s have a mobilizer</span>
      </div>
      {vacant.length ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-ui font-semibold">No one covering:</span>
          {vacant.map((u) => <Badge key={u.key} tone="bad">{u.name}</Badge>)}
        </div>
      ) : <p className="text-ui text-primary font-semibold">Every {noun} is covered.</p>}
    </Card>
  );
}

// The campaign's ground organisers: who they are, where they work, and how to reach them.
export default function Mobilizers({ campaign, onModal }) {
  const units = useUnits(campaign.id);
  const byCentre = campaign.operational_grain === "centre";
  const noun = byCentre ? "centre" : "ward";
  const { data, isLoading, error } = useMobilizers(campaign.id);
  const people = data || [];
  const placeOf = (m) => {
    if (!byCentre) return m.ward_name;
    if (!m.registration_centre) return null;
    return units.find((u) => u.registration_centre === m.registration_centre)?.name || "A centre with no target";
  };
  const action = <Button shape="rounded" onClick={() => onModal({ type: "mobilizer" })}>Add mobilizer</Button>;
  return (
    <>
      <WsHeader context="Field" title="Mobilizers" sub={`One lead per ${noun}. Mobilizers only see their own ${noun}.`} actions={action} />
      {isLoading && <KitLoading />}
      {error && <KitError error={error} />}
      {data && (
        <>
          {units.length > 0 && <Coverage units={units} mobilizers={people} noun={noun} />}
          <Card variant="outline" className="min-w-0 gap-3">
            <h2 className="text-card-title font-bold">Everyone</h2>
            <Table stack minWidth={560}>
              <THead><TR><TH>Name</TH><TH>{byCentre ? "Centre" : "Ward"}</TH><TH>Phone</TH><TH /></TR></THead>
              <TBody>
                {people.map((m) => (
                  <TR key={m.id}>
                    <TD>
                      <div className="flex items-center gap-2.5">
                        <span aria-hidden="true" className="flex size-9 flex-none items-center justify-center rounded-full bg-primary-tint text-meta font-extrabold text-primary">{initials(m.full_name)}</span>
                        <span className="font-semibold">{m.full_name}</span>
                      </div>
                    </TD>
                    <TD className={placeOf(m) ? undefined : "text-muted-foreground"}>{placeOf(m) || `No ${noun} yet`}</TD>
                    <TD className="text-muted-foreground tabular-nums">{m.phone || "None"}</TD>
                    <TD align="right">
                      <div className="flex justify-end gap-2">
                        <Button shape="rounded" size="sm" variant="quiet" onClick={() => onModal({ type: "assign-work", member: { role: "mobilizer", id: m.id } })} aria-label={`Assign work to ${m.full_name}`}>Assign work</Button>
                        <Button shape="rounded" size="sm" variant="quiet" onClick={() => onModal({ type: "mobilizer", mobilizer: m })}>Edit</Button>
                      </div>
                    </TD>
                  </TR>
                ))}
                {people.length === 0 && <TR><TD colSpan={4} className="text-muted-foreground">No mobilizers yet.</TD></TR>}
              </TBody>
            </Table>
          </Card>
        </>
      )}
    </>
  );
}
