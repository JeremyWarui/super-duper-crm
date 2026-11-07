// The console's Audit tab: who did what and when, read-only.
import { useState } from "react";
import { useAuditTrail } from "@/api/hooks";
import { useInstall } from "@/app/site";
import { Card } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { plural } from "@/lib/format";

const BLANK = { action: "", actor: "", since: "", until: "" };
const LIMIT = 200;
const detail = (d) => Object.entries(d || {}).map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`).join(", ");

export default function AuditTrail() {
  const { aspirant } = useInstall();
  const [filters, setFilters] = useState(BLANK);
  const set = (key) => (e) => setFilters((f) => ({ ...f, [key]: e.target.value }));
  const { data = [], isFetching, error } = useAuditTrail(filters);
  const count = `${plural(data.length, "event")}, newest first`;
  return (
    <div className="kit flex flex-col gap-4">
      <Card variant="outline" className="gap-3" role="search" aria-label="Filter the audit trail">
        <div className="grid gap-3 sm:grid-cols-4">
          <Field label="Action" hint="Its start, e.g. import or payment."><Input value={filters.action} onChange={set("action")} /></Field>
          <Field label="Who"><Input value={filters.actor} onChange={set("actor")} /></Field>
          <Field label="From"><Input type="date" value={filters.since} onChange={set("since")} /></Field>
          <Field label="To"><Input type="date" value={filters.until} onChange={set("until")} /></Field>
        </div>
      </Card>
      {error && <p role="alert" className="font-semibold text-destructive">{error.message}</p>}
      <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Audit trail">
        <p className="text-ui text-muted-foreground">
          {isFetching ? "Loading…" : data.length === LIMIT ? `${count}: the latest ${LIMIT}; narrow the filters to see older ones.` : `${count}.`}
        </p>
        <Table stack minWidth={720}>
          <THead><TR><TH>When</TH><TH>Who</TH><TH>Action</TH><TH>Detail</TH></TR></THead>
          <TBody>
            {data.map((e) => (
              <TR key={e.id}>
                <TD className="whitespace-nowrap">{new Date(e.created_at).toLocaleString()}</TD>
                <TD>{e.actor_name || "System"}</TD>
                <TD className="font-semibold">{aspirant ? e.action.replace(/^party\./, "site.") : e.action}</TD>
                <TD className="break-words text-muted-foreground">{detail(e.detail)}</TD>
              </TR>
            ))}
            {data.length === 0 && !isFetching && <TR><TD colSpan={4} className="text-muted-foreground">Nothing matches.</TD></TR>}
          </TBody>
        </Table>
      </Card>
    </div>
  );
}
