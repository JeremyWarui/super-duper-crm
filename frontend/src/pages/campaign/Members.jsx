// The party workspace's member list, for a coordinator: party members in their area, read-only.
import { useState } from "react";
import { useAreaMembers } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Pager } from "@/components/ui/pager";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { formatNumber as fmt } from "@/lib/format";
import { STATUS_LABEL, STATUS_TONE } from "@/lib/labels";
import { ErrorText } from "@/components/ui/error-text";
import { SlottedHeader } from "@/components/layout/AppPage";
import { LoadingText } from "@/components/ui/loading-text";


export default function Members() {
  const [page, setPage] = useState(1);
  const { data, isLoading, error } = useAreaMembers(page);
  return (
    <>
      <SlottedHeader context="Recruit" title="Party members" sub="Party members living in your area. View only: each time you open this list, it is recorded." />
      {isLoading && <LoadingText />}
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
                  <TD><Badge tone={STATUS_TONE[m.status]}>{STATUS_LABEL[m.status]}</Badge></TD>
                </TR>
              ))}
              {data.members.length === 0 && <TR><TD colSpan={5} className="text-muted-foreground">No party members in your area yet.</TD></TR>}
            </TBody>
          </Table>
          {data.total > data.page_size && (
            <Pager offset={(page - 1) * data.page_size} size={data.page_size} shown={data.members.length} total={data.total} noun="members" onChange={(offset) => setPage(offset / data.page_size + 1)} />
          )}
        </Card>
      )}
    </>
  );
}
