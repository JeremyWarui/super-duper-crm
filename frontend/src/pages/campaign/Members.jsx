// The party workspace's member list, for a coordinator: party members in their area, read-only.
import { useState } from "react";
import { useAreaMembers } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { formatNumber as fmt } from "@/lib/format";
import { STATUS_LABEL } from "../party/helpers";
import WsHeader, { KitLoading } from "./WsHeader";
import { ErrorText } from "@/components/ui/error-text";

const TONE = { pending: "warn", approved: "ok", suspended: "warn", rejected: "bad", withdrawn: "stone" };

export default function Members() {
  const [page, setPage] = useState(1);
  const { data, isLoading, error } = useAreaMembers(page);
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  return (
    <>
      <WsHeader context="Recruit" title="Party members" sub="Party members living in your area. View only: each time you open this list, it is recorded." />
      {isLoading && <KitLoading />}
      <ErrorText error={error} />
      {data && (
        <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Party members">
          <p className="text-ui text-muted-foreground">{fmt(data.total)} in your area</p>
          <Table stack minWidth={640}>
            <THead><TR><TH>Name</TH><TH>Phone</TH><TH>Ward</TH><TH>Polling station</TH><TH>Status</TH></TR></THead>
            <TBody>
              {data.members.map((m) => (
                <TR key={m.id}>
                  <TD className="font-semibold">{m.full_name}</TD>
                  <TD className="text-muted-foreground tabular-nums">{m.phone}</TD>
                  <TD>{m.ward_name}</TD>
                  <TD className="text-muted-foreground">{m.registration_centre_name || "None given"}</TD>
                  <TD><Badge tone={TONE[m.status]}>{STATUS_LABEL[m.status]}</Badge></TD>
                </TR>
              ))}
              {data.members.length === 0 && <TR><TD colSpan={5} className="text-muted-foreground">No party members in your area yet.</TD></TR>}
            </TBody>
          </Table>
          {pages > 1 && (
            <div className="flex flex-wrap items-center gap-2">
              <Button shape="rounded" size="sm" variant="quiet" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
              <span className="text-small text-muted-foreground">Page {fmt(page)} of {fmt(pages)}</span>
              <Button shape="rounded" size="sm" variant="quiet" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button>
            </div>
          )}
        </Card>
      )}
    </>
  );
}
