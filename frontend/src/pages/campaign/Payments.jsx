import { useState } from "react";
import { usePayments, usePayoutMode, useReconcileNow, useReconciliation } from "@/api/hooks";
import { useAuth } from "@/store/auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { FilterPills } from "@/components/ui/tabs";
import { formatDate, formatDateTime, formatKES, plural } from "../../lib/format";
import { ErrorText } from "@/components/ui/error-text";
import { StatTiles } from "@/components/ui/stat-tiles";
import { SlottedHeader } from "@/components/layout/AppPage";
import { LoadingText } from "@/components/ui/loading-text";
import { isLead } from "./helpers";

const TONE = { scheduled: "warn", sending: "info", paid: "ok", failed: "bad", cancelled: "stone" };
const LABEL = { scheduled: "Scheduled", sending: "Sending", paid: "Paid", failed: "To retry", cancelled: "Cancelled" };
const OPEN = ["scheduled", "failed"];  // still to go out: never sent, or a send that failed
const attention = (p) => p.status === "failed" || (p.status === "sending" && p.stuck);
// Decision 27: the role routing names approves, and never whoever scheduled it.
const mayApprove = (p, role, userId) => (p.approver_role || "manager") === role && p.scheduled_by !== userId;
const views = (approves) => ({
  All: () => true,
  "Awaiting my approval": (p) => OPEN.includes(p.status) && approves(p),
  "Needs attention": attention,
  Paid: (p) => p.status === "paid",
  Cancelled: (p) => p.status === "cancelled",
});

function Summary({ rows }) {
  const sum = (status) => rows.filter((p) => p.status === status).reduce((s, p) => s + p.amount_kes, 0);
  const scheduled = rows.filter((p) => p.status === "scheduled").length;
  const tiles = [
    ["Scheduled", formatKES(sum("scheduled")), `${scheduled} ready to release`],
    ["Needs attention", String(rows.filter(attention).length), "failed, or stuck while sending"],
    ["Paid", formatKES(sum("paid")), "this campaign so far"],
  ];
  return (
    <StatTiles tiles={tiles} />
  );
}

function RowActions({ p, onModal }) {
  if (OPEN.includes(p.status)) {
    return (
      <div className="flex flex-wrap justify-end gap-2">
        <Button shape="rounded" size="sm" onClick={() => onModal({ type: "payment-release", payments: [p] })}>{p.status === "failed" ? "Retry" : "Approve"}</Button>
        <Button shape="rounded" size="sm" variant="quiet" onClick={() => onModal({ type: "payment-paid", payment: p })}>Mark paid</Button>
        <Button shape="rounded" size="sm" variant="quiet" onClick={() => onModal({ type: "payment-decline", payment: p })}>Decline</Button>
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

// The payments register: coordinators and the manager schedule payments for done work; each
// waits for the role routing names (decision 27), who approves and releases, marks paid or
// declines it. Everyone else reads.
export default function Payments({ campaign, role, mine, onModal }) {
  const userId = useAuth((s) => s.user?.id);
  const canSchedule = !mine && (role === "coordinator" || (role === "manager" && campaign.kind !== "party"));
  const approves = (p) => !mine && mayApprove(p, role, userId);
  const VIEWS = views(approves);
  const { data, isLoading, error } = usePayments(campaign.id);
  const payout = usePayoutMode();
  const [view, setView] = useState("All");
  const rows = data || [];
  const canPay = rows.some(approves);
  const showActions = !mine && rows.some((p) => approves(p) || p.status === "scheduled");
  const shown = rows.filter(VIEWS[view]);
  const scheduled = rows.filter((p) => p.status === "scheduled" && approves(p));
  const actions = canSchedule || scheduled.length ? (
    <>
      {scheduled.length > 0 && <Button shape="rounded" variant="quiet" onClick={() => onModal({ type: "payment-release", payments: scheduled })}>Approve all awaiting me</Button>}
      {canSchedule && <Button shape="rounded" onClick={() => onModal({ type: "payment-schedule" })}>Schedule payment</Button>}
    </>
  ) : null;
  return (
    <>
      <SlottedHeader context={mine ? "My work" : "Money"} title={mine ? "My payments" : "Payments"} actions={actions} />
      {!mine && payout.data && !payout.data.moves_money && (
        <div role="note" className="flex flex-wrap gap-1 rounded-lg border border-[#F2D98A] bg-warn px-4 py-3 text-ui text-warn-foreground">
          <strong>Practice mode.</strong>
          <span>No money moves. Each released payment is marked paid under a PRACTICE reference.</span>
        </div>
      )}
      {isLoading && <LoadingText />}
      <ErrorText error={error} />
      {data && (
        <>
          <Summary rows={rows} />
          <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Payments">
            {!mine && <FilterPills label="Status" options={Object.keys(VIEWS)} value={view} onChange={setView} />}
            <Table stack minWidth={mine ? 560 : 760}>
              <THead><TR>
                <TH>Date</TH>{!mine && <TH>Payee</TH>}<TH>For</TH><TH align="right">Amount</TH><TH>Status</TH><TH>Reference</TH>{showActions && <TH className="relative"><span className="sr-only">Actions</span></TH>}
              </TR></THead>
              <TBody>
                {shown.map((p) => (
                  <TR key={p.id}>
                    <TD className="text-muted-foreground">{formatDate(p.paid_at || p.created_at)}</TD>
                    {!mine && <TD><div className="font-semibold">{p.recipient_name}</div><div className="text-small text-muted-foreground">{p.recipient_phone || "No phone"}</div></TD>}
                    <TD>{p.event_title || "None"}</TD>
                    <TD numeric className="font-bold">{formatKES(p.amount_kes)}</TD>
                    <TD>
                      <Badge tone={TONE[p.status]}>{LABEL[p.status]}</Badge>
                      {p.failure_reason && (canPay || p.status === "failed") && <div className={`mt-1 text-small ${p.status === "failed" ? "text-bad-foreground" : "text-warn-foreground"}`}>{p.failure_reason}</div>}
                    </TD>
                    <TD className="text-muted-foreground">{p.reference || "None"}</TD>
                    {showActions && <TD align="right">{approves(p) ? <RowActions p={p} onModal={onModal} /> : p.status === "scheduled" ? <span className="text-small text-muted-foreground">Awaiting the {p.approver_role === "candidate" ? "candidate" : "manager"}</span> : null}</TD>}
                  </TR>
                ))}
                {shown.length === 0 && <TR><TD colSpan={7} className="text-muted-foreground">{rows.length ? "No payments here." : "No payments yet."}</TD></TR>}
              </TBody>
            </Table>
          </Card>
          {!mine && isLead(role) && <Differences campaign={campaign} />}
        </>
      )}
    </>
  );
}


// Where the payments ledger and the payout provider's own records disagree; a person settles
// each one, the check changes nothing.
function Differences({ campaign }) {
  const found = useReconciliation(campaign.id);
  const now = useReconcileNow();
  const run = found.data?.last_run;
  const rows = found.data?.differences || [];
  return (
    <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Differences with the payout provider">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-h3 font-bold">Differences with the payout provider</h2>
        <Button shape="rounded" size="sm" variant="quiet" disabled={now.isPending} onClick={() => now.mutate(campaign.id)}>{now.isPending ? "Checking…" : "Check now"}</Button>
      </div>
      <ErrorText error={found.error || now.error} />
      <p className="text-small text-muted-foreground">
        {!run ? "Not checked yet. It runs once a day." : run.status === "practice" ? run.detail : run.status === "failed" ? `The last check failed: ${run.detail}` : `Last checked ${formatDateTime(run.created_at)}: ${plural(run.checked, "payment")} compared.`}
      </p>
      {run && run.status !== "practice" && run.status !== "failed" && (rows.length === 0 ? <p className="font-semibold text-ok-foreground">The ledger matches the provider.</p> : (
        <Table stack minWidth={640}>
          <THead><TR><TH>Payee</TH><TH>Here</TH><TH>Provider</TH><TH>What differs</TH></TR></THead>
          <TBody>
            {rows.map((d) => (
              <TR key={d.reference}>
                <TD><div className="font-semibold">{d.recipient_name || "Unknown"}</div><div className="text-small text-muted-foreground">{d.reference}</div></TD>
                <TD>{d.ledger}</TD>
                <TD>{d.provider}</TD>
                <TD>{d.detail}</TD>
              </TR>
            ))}
          </TBody>
        </Table>
      ))}
    </Card>
  );
}
