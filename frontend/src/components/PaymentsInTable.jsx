// Money paid in by M-Pesa, newest first; a code a payer reported is confirmed against the M-Pesa
// statement, or rejected with a reason.
import { useState } from "react";
import { useDecidePaymentIn, usePaymentsIn } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { FilterPills } from "@/components/ui/tabs";
import { formatKES } from "../lib/format";
import { ErrorText } from "@/components/ui/error-text";

const LABEL = { pending: "Waiting for the phone", paid: "Paid", to_confirm: "To confirm", failed: "Failed", rejected: "Rejected" };
const TONE = { pending: "stone", paid: "ok", to_confirm: "warn", failed: "bad", rejected: "bad" };
const PURPOSE = { contribution: "Contribution", nomination_fee: "Nomination fee" };
const FILTERS = { "To confirm": "to_confirm", Paid: "paid", All: "" };
const day = (iso) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });

/** A workspace's list with `campaignId`; the party's without. */
export default function PaymentsInTable({ campaignId }) {
  const [view, setView] = useState("To confirm");
  const list = usePaymentsIn(campaignId, FILTERS[view]);
  const decide = useDecidePaymentIn(campaignId);
  const [rejecting, setRejecting] = useState(null);
  const [reason, setReason] = useState("");
  const rows = list.data || [];
  const total = rows.filter((r) => r.status === "paid").reduce((sum, r) => sum + r.amount_kes, 0);
  return (
    <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Payments in">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <FilterPills label="Show" options={Object.keys(FILTERS)} value={view} onChange={setView} />
        {view !== "To confirm" && rows.length ? <span className="text-ui text-muted-foreground">Paid in this list: {formatKES(total)}</span> : null}
      </div>
      <ErrorText error={list.error} />
      <ErrorText error={decide.error} />
      <Table stack minWidth={720}>
        <THead><TR><TH>Date</TH><TH>Payer</TH><TH>For</TH><TH align="right">Amount</TH><TH>M-Pesa code</TH><TH>Status</TH><TH><span className="sr-only">Actions</span></TH></TR></THead>
        <TBody>
          {rows.map((r) => (
            <TR key={r.id}>
              <TD>{day(r.created_at)}</TD>
              <TD><div className="font-semibold">{r.payer_name}</div><div className="text-small text-muted-foreground">{r.payer_phone}</div></TD>
              <TD>{PURPOSE[r.purpose]}</TD>
              <TD align="right" className="tabular-nums">{formatKES(r.amount_kes)}</TD>
              <TD className="font-mono">{r.mpesa_code || "—"}</TD>
              <TD><Badge tone={TONE[r.status]}>{LABEL[r.status]}</Badge>{r.reason ? <div className="text-small text-muted-foreground">{r.reason}</div> : null}</TD>
              <TD align="right">
                {r.status === "to_confirm" && rejecting !== r.id ? (
                  <span className="inline-flex flex-wrap justify-end gap-2">
                    <Button size="sm" shape="rounded" disabled={decide.isPending} onClick={() => decide.mutate({ id: r.id })} aria-label={`Confirm ${r.mpesa_code}`}>Confirm</Button>
                    <Button size="sm" shape="rounded" variant="quiet" onClick={() => { setReason(""); setRejecting(r.id); }} aria-label={`Reject ${r.mpesa_code}`}>Reject</Button>
                  </span>
                ) : null}
                {rejecting === r.id ? (
                  <span className="inline-flex flex-wrap items-center justify-end gap-2">
                    <Input aria-label={`Why reject ${r.mpesa_code}`} value={reason} placeholder="Not on the statement" onChange={(e) => setReason(e.target.value)} />
                    <Button size="sm" shape="rounded" disabled={!reason.trim() || decide.isPending} onClick={() => decide.mutate({ id: r.id, reason: reason.trim() }, { onSuccess: () => setRejecting(null) })}>Reject</Button>
                    <Button size="sm" shape="rounded" variant="quiet" onClick={() => setRejecting(null)}>Keep</Button>
                  </span>
                ) : null}
              </TD>
            </TR>
          ))}
          {!list.isLoading && rows.length === 0 ? <TR><TD colSpan={7} className="text-muted-foreground">Nothing here.</TD></TR> : null}
        </TBody>
      </Table>
    </Card>
  );
}
