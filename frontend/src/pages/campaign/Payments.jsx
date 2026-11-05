import { useState } from "react";
import { usePayments, usePayoutMode } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { FilterPills } from "@/components/ui/tabs";
import { kes } from "./helpers";
import WsHeader, { KitError, KitLoading } from "./WsHeader";

const TONE = { scheduled: "warn", sending: "info", paid: "ok", failed: "bad", cancelled: "stone" };
const OPEN = ["scheduled", "failed"];  // still to go out: never sent, or a send that failed
const attention = (p) => p.status === "failed" || (p.status === "sending" && p.stuck);
const VIEWS = {
  All: () => true,
  "To release": (p) => OPEN.includes(p.status),
  "Needs attention": attention,
  Paid: (p) => p.status === "paid",
  Cancelled: (p) => p.status === "cancelled",
};

function Summary({ rows }) {
  const sum = (status) => rows.filter((p) => p.status === status).reduce((s, p) => s + p.amount_kes, 0);
  const scheduled = rows.filter((p) => p.status === "scheduled").length;
  const tiles = [
    ["Scheduled", kes(sum("scheduled")), `${scheduled} ready to release`],
    ["Needs attention", String(rows.filter(attention).length), "failed, or stuck while sending"],
    ["Paid", kes(sum("paid")), "this campaign so far"],
  ];
  return (
    <section aria-label="Summary" className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4">
      {tiles.map(([label, value, note]) => (
        <Card key={label} variant="tile">
          <span className="text-ui text-muted-foreground">{label}</span>
          <span className="font-display text-[28px] leading-tight font-extrabold tabular-nums">{value}</span>
          <span className="text-small text-muted-foreground">{note}</span>
        </Card>
      ))}
    </section>
  );
}

function RowActions({ p, onModal }) {
  if (OPEN.includes(p.status)) {
    return (
      <div className="flex justify-end gap-2">
        <Button shape="rounded" size="sm" onClick={() => onModal({ type: "payment-release", payments: [p] })}>Release</Button>
        <Button shape="rounded" size="sm" variant="quiet" onClick={() => onModal({ type: "payment-paid", payment: p })}>Mark paid</Button>
        <Button shape="rounded" size="sm" variant="quiet" onClick={() => onModal({ type: "payment-cancel", payment: p })}>Cancel</Button>
      </div>
    );
  }
  if (p.status !== "sending") return null;
  return p.stuck ? (
    <div className="flex justify-end gap-2">
      <Button shape="rounded" size="sm" variant="quiet" onClick={() => onModal({ type: "payment-paid", payment: p })}>Mark paid</Button>
      <Button shape="rounded" size="sm" variant="quiet" onClick={() => onModal({ type: "payment-notsent", payment: p })}>Didn't go out</Button>
    </div>
  ) : <span className="text-small text-muted-foreground">Waiting for the provider…</span>;
}

// The payments register: the manager and coordinators schedule; only the manager releases,
// marks paid and cancels; everyone else reads.
export default function Payments({ campaign, role, mine, onModal }) {
  const canSchedule = !mine && (role === "manager" || role === "coordinator");
  const canPay = role === "manager" && !mine;
  const { data, isLoading, error } = usePayments(campaign.id);
  const payout = usePayoutMode();
  const [view, setView] = useState("All");
  const rows = data || [];
  const shown = rows.filter(VIEWS[view]);
  const scheduled = rows.filter((p) => p.status === "scheduled");
  const actions = canSchedule ? (
    <>
      {canPay && scheduled.length > 0 && <Button shape="rounded" variant="quiet" onClick={() => onModal({ type: "payment-release", payments: scheduled })}>Release all scheduled</Button>}
      <Button shape="rounded" onClick={() => onModal({ type: "payment-schedule" })}>Schedule payment</Button>
    </>
  ) : null;
  return (
    <>
      <WsHeader context={mine ? "My work" : "Money"} title={mine ? "My payments" : "Payments"} actions={actions} />
      {!mine && payout.data && !payout.data.moves_money && (
        <div role="note" className="flex flex-wrap gap-1 rounded-lg border border-[#F2D98A] bg-warn px-4 py-3 text-ui text-warn-foreground">
          <strong>Practice mode.</strong>
          <span>No money moves. Each released payment is marked paid under a PRACTICE reference.</span>
        </div>
      )}
      {isLoading && <KitLoading />}
      {error && <KitError error={error} />}
      {data && (
        <>
          <Summary rows={rows} />
          <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Payments">
            {!mine && <FilterPills label="Status" options={Object.keys(VIEWS)} value={view} onChange={setView} />}
            <Table minWidth={mine ? 560 : 760}>
              <THead><TR>
                <TH>Date</TH>{!mine && <TH>Mobilizer</TH>}<TH>Event</TH><TH align="right">Amount</TH><TH>Status</TH><TH>Reference</TH>{canPay && <TH className="relative"><span className="sr-only">Actions</span></TH>}
              </TR></THead>
              <TBody>
                {shown.map((p) => (
                  <TR key={p.id}>
                    <TD className="text-muted-foreground">{new Date(p.paid_at || p.created_at).toLocaleDateString()}</TD>
                    {!mine && <TD><div className="font-semibold">{p.recipient_name}</div><div className="text-small text-muted-foreground">{p.recipient_phone || "No phone"}</div></TD>}
                    <TD>{p.event_title || "None"}</TD>
                    <TD numeric className="font-bold">{kes(p.amount_kes)}</TD>
                    <TD>
                      <Badge tone={TONE[p.status]} className="capitalize">{p.status}</Badge>
                      {p.failure_reason && (canPay || p.status === "failed") && <div className={`mt-1 text-small ${p.status === "failed" ? "text-bad-foreground" : "text-warn-foreground"}`}>{p.failure_reason}</div>}
                    </TD>
                    <TD className="text-muted-foreground">{p.reference || "None"}</TD>
                    {canPay && <TD align="right"><RowActions p={p} onModal={onModal} /></TD>}
                  </TR>
                ))}
                {shown.length === 0 && <TR><TD colSpan={7} className="text-muted-foreground">{rows.length ? "No payments here." : "No payments yet."}</TD></TR>}
              </TBody>
            </Table>
          </Card>
        </>
      )}
    </>
  );
}
