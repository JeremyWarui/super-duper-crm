// The console's Audit tab: who did what and when, read-only.
import { rowsOf, useAuditPages } from "@/api/hooks";
import { useInstall } from "@/app/site";
import { Card } from "@/components/ui/card";
import { LoadMore } from "@/components/ui/load-more";
import { Field, Input } from "@/components/ui/input";
import { EmptyRow, Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { ErrorText } from "@/components/ui/error-text";
import { LoadingText } from "@/components/ui/loading-text";
import { formatDateTime } from "@/lib/format";
import { useForm } from "@/lib/form";

const BLANK = { action: "", actor: "", since: "", until: "" };
const detail = (d) => Object.entries(d || {}).map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`).join(", ");

export default function AuditTrail() {
  const { aspirant } = useInstall();
  const [filters, , set] = useForm(BLANK);
  const pages = useAuditPages(filters);
  const { isFetching, isFetchingNextPage, error } = pages;
  const data = rowsOf(pages.data);
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
      <ErrorText error={error} />
      <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Audit trail">
        <p className="text-ui text-muted-foreground">Newest first.</p>
        <Table stack minWidth={720}>
          <THead><TR><TH>When</TH><TH>Who</TH><TH>Action</TH><TH>Detail</TH></TR></THead>
          <TBody>
            {data.map((e) => (
              <TR key={e.id}>
                <TD className="whitespace-nowrap">{formatDateTime(e.created_at)}</TD>
                <TD>{e.actor_name || "System"}</TD>
                <TD className="font-semibold">{aspirant ? e.action.replace(/^party\./, "site.") : e.action}</TD>
                <TD className="break-words text-muted-foreground">{detail(e.detail)}</TD>
              </TR>
            ))}
            {data.length === 0 && !isFetching && <EmptyRow>Nothing matches.</EmptyRow>}
          </TBody>
        </Table>
        {isFetching && !isFetchingNextPage ? <LoadingText className="text-ui" /> : null}
        <LoadMore shown={data.length} noun={data.length === 1 ? "event" : "events"} hasMore={!!pages.hasNextPage} loading={isFetchingNextPage} onMore={() => pages.fetchNextPage()} />
      </Card>
    </div>
  );
}
