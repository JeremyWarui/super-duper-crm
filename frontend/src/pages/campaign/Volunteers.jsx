// The volunteers who signed up for this campaign on the candidate's website page; the candidate,
// the manager and coordinators in their area mark each active or inactive; the candidate or the
// manager erases a withdrawn volunteer's details on request.
import { useState } from "react";
import { useCampaignVolunteers, useErase, useUpdateCampaignVolunteer } from "@/api/hooks";
import EraseButton from "@/components/EraseButton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { FilterPills } from "@/components/ui/tabs";
import { useCopy } from "@/copy";
import { CONTACT_LABEL, VOLUNTEER_STATUS_LABEL, VOLUNTEER_STATUS_TONE, helpsWith, professionOf } from "@/lib/labels";
import { ErrorText } from "@/components/ui/error-text";
import { StatTiles } from "@/components/ui/stat-tiles";
import { SlottedHeader } from "@/components/layout/AppPage";
import { LoadingText } from "@/components/ui/loading-text";
import { isLead } from "./helpers";

const FILTERS = { All: null, Interested: "interested", Active: "active", Inactive: "inactive" };

export default function Volunteers({ campaign, role }) {
  const copy = useCopy();
  const { data, isLoading, error } = useCampaignVolunteers(campaign.id);
  const update = useUpdateCampaignVolunteer(campaign.id);
  const erase = useErase(campaign.id, "volunteers");
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
      <SlottedHeader context="Field" title="Volunteers" sub="People who offered to help on the candidate's website page." />
      {isLoading && <LoadingText />}
      <ErrorText error={error} />
      {data && (
        <>
          <StatTiles tiles={tiles} />
          <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Volunteers">
            <div className="flex flex-wrap items-center gap-3">
              <FilterPills label="Status" options={Object.keys(FILTERS)} value={filter} onChange={setFilter} />
              <Input type="search" aria-label="Search volunteers" placeholder="Name, phone or ward" className="max-w-xs" value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
            <ErrorText error={update.error} />
            <ErrorText error={erase.error} />
            <Table stack minWidth={900}>
              <THead><TR><TH>Name</TH><TH>Phone</TH><TH>Ward</TH><TH>Helps with</TH><TH>Profession</TH><TH>Contact by</TH><TH>Status</TH><TH className="relative"><span className="sr-only">Actions</span></TH></TR></THead>
              <TBody>
                {shown.map((v) => {
                  const name = `${v.first_name} ${v.last_name}`.trim();
                  const next = v.status === "active" ? "inactive" : "active";
                  return (
                    <TR key={v.id}>
                      <TD className="font-semibold">{name}</TD>
                      <TD className="text-muted-foreground">{v.phone}</TD>
                      <TD>{v.ward.name}{v.registration_centre && <div className="text-small text-muted-foreground">{v.registration_centre.name}</div>}</TD>
                      <TD>{helpsWith(v.interests, v.interest_other) || "None given"}</TD>
                      <TD className="text-muted-foreground">{professionOf(v) || "None given"}</TD>
                      <TD className="text-muted-foreground">{CONTACT_LABEL[v.preferred_contact]}</TD>
                      <TD><Badge tone={v.erased_at ? "stone" : VOLUNTEER_STATUS_TONE[v.status]}>{v.erased_at ? "Erased" : VOLUNTEER_STATUS_LABEL[v.status]}</Badge></TD>
                      <TD align="right">
                        {v.status !== "withdrawn" ? (
                          <Button shape="rounded" size="sm" variant="quiet" disabled={update.isPending} onClick={() => update.mutate({ id: v.id, status: next })}>
                            {next === "active" ? "Make active" : "Make inactive"}
                          </Button>
                        ) : !v.erased_at && isLead(role) ? (
                          <EraseButton name={name} pending={erase.isPending} onErase={(done) => erase.mutate(v.id, { onSuccess: done })} />
                        ) : null}
                      </TD>
                    </TR>
                  );
                })}
                {shown.length === 0 && <TR><TD colSpan={8} className="text-muted-foreground">{all.length ? "Nobody matches." : copy.volunteersNone}</TD></TR>}
              </TBody>
            </Table>
          </Card>
        </>
      )}
    </>
  );
}
