// Work given to mobilizers and agents: assigned, then marked done (which makes it payable), or
// cancelled.
import { useState } from "react";
import { useAssignments, useSettleAssignment } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { FilterPills } from "@/components/ui/tabs";
import { kes } from "./helpers";
import WsHeader, { KitError, KitLoading } from "./WsHeader";

const VIEWS = { "To mark done": "assigned", Done: "done", Cancelled: "cancelled" };
const TONE = { assigned: "warn", done: "ok", cancelled: "stone" };
const KIND = { event: "Event", ward_work: "Ward work", activity: "Activity" };

export default function Assignments({ campaign, onModal }) {
  const [view, setView] = useState("To mark done");
  const rows = useAssignments(campaign.id, VIEWS[view]);
  const settle = useSettleAssignment();
  const list = rows.data || [];
  const open = view === "To mark done";
  const action = <Button shape="rounded" onClick={() => onModal({ type: "assign-work" })}>Assign work</Button>;
  return (
    <>
      <WsHeader context="Field" title="Assignments" sub="Paid work for mobilizers and agents. Mark it done once it happened; then it can be paid." actions={action} />
      <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Assignments">
        <FilterPills label="Status" options={Object.keys(VIEWS)} value={view} onChange={setView} />
        {settle.error && <p role="alert" className="font-semibold text-destructive">{settle.error.message}</p>}
        {rows.isLoading && <KitLoading />}
        {rows.error && <KitError error={rows.error} />}
        {rows.data && (
          <Table stack minWidth={720}>
            <THead><TR><TH>Work</TH><TH>Who</TH><TH>Where</TH><TH align="right">Amount</TH><TH>Status</TH>{open && <TH className="relative"><span className="sr-only">Actions</span></TH>}</TR></THead>
            <TBody>
              {list.map((a) => (
                <TR key={a.id}>
                  <TD><div className="font-semibold">{a.label}</div><div className="text-small text-muted-foreground">{KIND[a.kind]}</div></TD>
                  <TD>{a.member_name}<div className="text-small text-muted-foreground">{a.member_role === "agent" ? "Agent" : "Mobilizer"}</div></TD>
                  <TD>{a.centre_name || a.ward_name || "None"}{a.centre_name && <div className="text-small text-muted-foreground">{a.ward_name}</div>}</TD>
                  <TD numeric className="font-bold">{kes(a.amount_kes)}</TD>
                  <TD><Badge tone={TONE[a.status]}>{a.status === "assigned" ? "Assigned" : a.status === "done" ? "Done" : "Cancelled"}</Badge></TD>
                  {open && (
                    <TD align="right">
                      <div className="flex justify-end gap-2">
                        <Button shape="rounded" size="sm" disabled={settle.isPending} onClick={() => settle.mutate({ id: a.id, outcome: "done" })} aria-label={`Mark ${a.label} done`}>Mark done</Button>
                        <Button shape="rounded" size="sm" variant="quiet" disabled={settle.isPending} onClick={() => settle.mutate({ id: a.id, outcome: "cancel" })} aria-label={`Cancel ${a.label}`}>Cancel</Button>
                      </div>
                    </TD>
                  )}
                </TR>
              ))}
              {list.length === 0 && <TR><TD colSpan={6} className="text-muted-foreground">{open ? "Nothing waits to be marked done." : "None yet."}</TD></TR>}
            </TBody>
          </Table>
        )}
      </Card>
    </>
  );
}
