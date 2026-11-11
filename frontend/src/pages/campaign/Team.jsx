// Everyone with a login on the campaign; the candidate and manager add coordinators and comms,
// set each coordinator's area and take staff off. Only the candidate adds or replaces the manager.
import { useState } from "react";
import { useRemoveStaff, useTeam } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Confirm } from "@/components/ui/confirm";
import { Card } from "@/components/ui/card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { FilterPills } from "@/components/ui/tabs";
import { ROLE_LABEL } from "@/lib/labels";
import { ErrorText } from "@/components/ui/error-text";
import { StatTiles } from "@/components/ui/stat-tiles";
import { SlottedHeader } from "@/components/layout/AppPage";
import { LoadingText } from "@/components/ui/loading-text";
import { isLead } from "./helpers";
import { displayName } from "@/lib/format";

const ORDER = ["candidate", "manager", "coordinator", "comms", "mobilizer", "agent"];
const TONE = { candidate: "ink", manager: "primary", coordinator: "tint", comms: "info", mobilizer: "stone", agent: "stone" };
const VIEWS = {
  Everyone: () => true,
  Leads: (p) => isLead(p.role),
  Coordinators: (p) => p.role === "coordinator",
  Comms: (p) => p.role === "comms",
  Field: (p) => p.role === "mobilizer" || p.role === "agent",
};

export default function Team({ campaign, role, onModal }) {
  const { data, isLoading, error } = useTeam(campaign.id);
  const [view, setView] = useState("Everyone");
  const remove = useRemoveStaff();
  const people = [...(data || [])].sort((a, b) => ORDER.indexOf(a.role) - ORDER.indexOf(b.role) || displayName(a).localeCompare(displayName(b)));
  const manager = people.find((p) => p.role === "manager");
  const shown = people.filter(VIEWS[view]);
  const count = (r) => people.filter((p) => p.role === r).length;
  const actions = (
    <>
      <Button shape="rounded" variant="quiet" onClick={() => onModal({ type: "staff", role: "coordinator" })}>Add coordinator</Button>
      <Button shape="rounded" variant="quiet" onClick={() => onModal({ type: "staff", role: "comms" })}>Add comms officer</Button>
      {role === "candidate" && <Button shape="rounded" onClick={() => onModal({ type: "manager", sitting: manager })}>{manager ? "Replace manager" : "Add manager"}</Button>}
    </>
  );
  const tiles = [
    ["Manager", manager ? "In place" : "None yet", manager ? "runs the day-to-day" : "the candidate adds one"],
    ["Coordinators", String(count("coordinator")), "each limited to their area"],
    ["Comms officers", String(count("comms")), "events, messages and the website"],
    ["Field team", String(count("mobilizer") + count("agent")), "mobilizers and agents"],
  ];
  return (
    <>
      <SlottedHeader context="People" title="Team" sub="Everyone with a login on this campaign." actions={actions} />
      {isLoading && <LoadingText />}
      <ErrorText error={error} />
      {data && (
        <>
          <StatTiles tiles={tiles} valueClassName="truncate text-[24px] leading-tight" />
          {!manager && role === "candidate" && (
            <div role="note" className="rounded-lg border border-[#F2D98A] bg-warn px-4 py-3 text-ui text-warn-foreground">
              This campaign has no manager yet. Add one to run the day-to-day.
            </div>
          )}
          <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Team">
            <FilterPills label="Role" options={Object.keys(VIEWS)} value={view} onChange={setView} />
            <Table stack minWidth={560}>
              <THead><TR><TH>Name</TH><TH>Username</TH><TH>Role</TH><TH className="relative"><span className="sr-only">Actions</span></TH></TR></THead>
              <TBody>
                {shown.map((p) => (
                  <TR key={p.id}>
                    <TD className="font-semibold">{displayName(p)}</TD>
                    <TD className="text-muted-foreground">{p.username}</TD>
                    <TD>
                      <Badge tone={TONE[p.role]}>{ROLE_LABEL[p.role]}</Badge>
                      {!p.is_active && <span className="ml-2 text-small text-muted-foreground">turned off</span>}
                    </TD>
                    <TD align="right">
                      <span className="inline-flex flex-wrap items-center justify-end gap-2">
                        {p.role === "coordinator" && (
                          <Button shape="rounded" size="sm" variant="quiet" onClick={() => onModal({ type: "area", person: p })} aria-label={`Area for ${displayName(p)}`}>Area</Button>
                        )}
                        {(p.role === "coordinator" || p.role === "comms") && (
                          <Confirm size="sm" variant="quiet" yesVariant="primary" label="Take off" ariaLabel={`Take ${displayName(p)} off the team`}
                            question="Their login is turned off." yes={remove.isPending ? "Taking off…" : "Take off"} no="Keep" pending={remove.isPending}
                            onAsk={() => remove.reset()} onConfirm={(done) => remove.mutate({ campaign: campaign.id, user: p.id }, { onSuccess: done })} />
                        )}
                      </span>
                      {remove.variables?.user === p.id && <ErrorText error={remove.error} className="mt-1 text-small" />}
                    </TD>
                  </TR>
                ))}
                {shown.length === 0 && <TR><TD colSpan={4} className="text-muted-foreground">Nobody here yet.</TD></TR>}
              </TBody>
            </Table>
          </Card>
        </>
      )}
    </>
  );
}
