// The volunteers who signed up for this campaign on the candidate's website page; the candidate,
// the manager and coordinators in their area mark each active or inactive.
import { useState } from "react";
import { useCampaignVolunteers, useUpdateCampaignVolunteer } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { FilterPills } from "@/components/ui/tabs";
import { AREA_LABEL, CONTACT_LABEL, PROFESSION_LABEL } from "../party/helpers";
import WsHeader, { KitError, KitLoading } from "./WsHeader";

const TONE = { interested: "warn", active: "ok", inactive: "bad" };
const LABEL = { interested: "Interested", active: "Active", inactive: "Inactive" };
const FILTERS = { All: null, Interested: "interested", Active: "active", Inactive: "inactive" };

function helps(v) {
  return v.interests.map((a) => (a === "other" ? v.interest_other : AREA_LABEL[a])).filter(Boolean).join(", ");
}

export default function Volunteers({ campaign }) {
  const { data, isLoading, error } = useCampaignVolunteers(campaign.id);
  const update = useUpdateCampaignVolunteer(campaign.id);
  const [filter, setFilter] = useState("All");
  const [q, setQ] = useState("");
  const all = data || [];
  const needle = q.trim().toLowerCase();
  const shown = all.filter((v) => (!FILTERS[filter] || v.status === FILTERS[filter]) && (!needle || `${v.first_name} ${v.last_name} ${v.phone} ${v.ward.name}`.toLowerCase().includes(needle)));
  const count = (s) => all.filter((v) => v.status === s).length;
  const tiles = [
    ["Signed up", String(all.length), "on the candidate's website page"],
    ["Interested", String(count("interested")), "waiting for a first call"],
    ["Active", String(count("active")), "helping now"],
  ];
  return (
    <>
      <WsHeader context="Field" title="Volunteers" sub="People who offered to help on the candidate's website page." />
      {isLoading && <KitLoading />}
      {error && <KitError error={error} />}
      {data && (
        <>
          <section aria-label="Summary" className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4">
            {tiles.map(([label, value, note]) => (
              <Card key={label} variant="tile">
                <span className="text-ui text-muted-foreground">{label}</span>
                <span className="font-display text-[28px] leading-tight font-extrabold tabular-nums">{value}</span>
                <span className="text-small text-muted-foreground">{note}</span>
              </Card>
            ))}
          </section>
          <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Volunteers">
            <div className="flex flex-wrap items-center gap-3">
              <FilterPills label="Status" options={Object.keys(FILTERS)} value={filter} onChange={setFilter} />
              <Input type="search" aria-label="Search volunteers" placeholder="Name, phone or ward" className="max-w-xs" value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
            {update.isError && <p role="alert" className="font-semibold text-destructive">{update.error.message}</p>}
            <Table stack minWidth={900}>
              <THead><TR><TH>Name</TH><TH>Phone</TH><TH>Ward</TH><TH>Helps with</TH><TH>Profession</TH><TH>Contact by</TH><TH>Status</TH><TH className="relative"><span className="sr-only">Actions</span></TH></TR></THead>
              <TBody>
                {shown.map((v) => {
                  const name = `${v.first_name} ${v.last_name}`;
                  const next = v.status === "active" ? "inactive" : "active";
                  return (
                    <TR key={v.id}>
                      <TD className="font-semibold">{name}</TD>
                      <TD className="text-muted-foreground">{v.phone}</TD>
                      <TD>{v.ward.name}{v.registration_centre && <div className="text-small text-muted-foreground">{v.registration_centre.name}</div>}</TD>
                      <TD>{helps(v) || "None given"}</TD>
                      <TD className="text-muted-foreground">{v.profession === "other" ? v.profession_other : PROFESSION_LABEL[v.profession] || "None given"}</TD>
                      <TD className="text-muted-foreground">{CONTACT_LABEL[v.preferred_contact]}</TD>
                      <TD><Badge tone={TONE[v.status]}>{LABEL[v.status]}</Badge></TD>
                      <TD align="right">
                        <Button shape="rounded" size="sm" variant="quiet" disabled={update.isPending} onClick={() => update.mutate({ id: v.id, status: next })}>
                          {next === "active" ? "Make active" : "Make inactive"}
                        </Button>
                      </TD>
                    </TR>
                  );
                })}
                {shown.length === 0 && <TR><TD colSpan={8} className="text-muted-foreground">{all.length ? "Nobody matches." : "None yet. Volunteers sign up on the candidate's page on the party website."}</TD></TR>}
              </TBody>
            </Table>
          </Card>
        </>
      )}
    </>
  );
}
