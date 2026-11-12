import { useMobilizers } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { EmptyRow, Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { holderOf, unitOf, useUnits } from "./helpers";
import { initials } from "@/lib/format";
import { ErrorText } from "@/components/ui/error-text";
import { SlottedHeader } from "@/components/layout/AppPage";
import { LoadingText } from "@/components/ui/loading-text";
import CoverageCard from "./CoverageCard";

// The campaign's ground organisers: who they are, where they work, and how to reach them.
export default function Mobilizers({ campaign, onModal }) {
  const units = useUnits(campaign.id);
  const { byCentre, noun, Noun } = unitOf(campaign);
  const { data, isLoading, error } = useMobilizers(campaign.id);
  const people = data || [];
  const vacant = units.filter((u) => !holderOf(people, u));
  const workplace = (m) => {
    if (!byCentre) return m.ward_name;
    if (!m.registration_centre) return null;
    return units.find((u) => u.registration_centre === m.registration_centre)?.name || "A centre with no target";
  };
  const action = <Button onClick={() => onModal({ type: "mobilizer" })}>Add mobilizer</Button>;
  return (
    <>
      <SlottedHeader context="Field" title="Mobilizers" sub={`One lead per ${noun}. Mobilizers only see their own ${noun}.`} actions={action} />
      {isLoading && <LoadingText />}
      <ErrorText error={error} />
      {data && (
        <>
          {units.length > 0 && (
            <CoverageCard title="Coverage" count={`${units.length - vacant.length} of ${units.length} ${noun}s have a mobilizer`}
              gaps={vacant.map((u) => ({ key: u.key, label: u.name }))} done={`Every ${noun} is covered.`} />
          )}
          <Card variant="outline" className="min-w-0 gap-3">
            <CardTitle>Everyone</CardTitle>
            <Table stack minWidth={560}>
              <THead><TR><TH>Name</TH><TH>{Noun}</TH><TH>Phone</TH><TH /></TR></THead>
              <TBody>
                {people.map((m) => (
                  <TR key={m.id}>
                    <TD>
                      <div className="flex items-center gap-2.5">
                        <span aria-hidden="true" className="flex size-9 flex-none items-center justify-center rounded-full bg-primary-tint text-meta font-extrabold text-primary">{initials(m.full_name)}</span>
                        <span className="font-semibold">{m.full_name}</span>
                      </div>
                    </TD>
                    <TD className={workplace(m) ? undefined : "text-muted-foreground"}>{workplace(m) || `No ${noun} yet`}</TD>
                    <TD className="text-muted-foreground tabular-nums">{m.phone || "None"}</TD>
                    <TD align="right">
                      <div className="flex justify-end gap-2">
                        <Button size="sm" variant="quiet" onClick={() => onModal({ type: "assign-work", member: { role: "mobilizer", id: m.id } })} aria-label={`Assign work to ${m.full_name}`}>Assign work</Button>
                        <Button size="sm" variant="quiet" onClick={() => onModal({ type: "mobilizer", mobilizer: m })}>Edit</Button>
                      </div>
                    </TD>
                  </TR>
                ))}
                {people.length === 0 && <EmptyRow>No mobilizers yet.</EmptyRow>}
              </TBody>
            </Table>
          </Card>
        </>
      )}
    </>
  );
}
