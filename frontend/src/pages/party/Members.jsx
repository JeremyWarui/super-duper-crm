// The membership officer's register: filter, page through, open a member, move their status, and
// erase a withdrawn or rejected member's details on request.
import { useState } from "react";
import {
  exportPartyMembers,
  useEraseMember,
  useMoveMember,
  usePartyMember,
  usePartyMembers,
} from "@/api/hooks";
import { SlottedHeader } from "@/components/layout/AppPage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Confirm } from "@/components/ui/confirm";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { ErrorText } from "@/components/ui/error-text";
import { FormActions } from "@/components/ui/form-actions";
import { Input } from "@/components/ui/input";
import { LoadingText } from "@/components/ui/loading-text";
import { Pager } from "@/components/ui/pager";
import { RowButton, TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { formatDate, placeOf } from "@/lib/format";
import { STATUS_LABEL, STATUS_TONE } from "@/lib/labels";
import { MOVES, PAGE_SIZE } from "./helpers";
import { Linked, MoveButtons, StatusFilter, useLinkedRecord, useRegister } from "./register";
import PlaceCascade, { NO_PLACE } from "@/components/PlaceCascade";

const ERASABLE = ["withdrawn", "rejected"];

function Erase({ member }) {
  const erase = useEraseMember();
  if (member.erased_at) return <p className="text-ui text-muted-foreground">Details erased on {formatDate(member.erased_at)}.</p>;
  if (!ERASABLE.includes(member.status)) return null;
  return (
    <>
      <FormActions>
        <Confirm label="Erase their details" question="Erase their name, phone, email and account for good?" yes="Yes, erase"
          pending={erase.isPending} onConfirm={() => erase.mutate(member.id)} />
      </FormActions>
      <ErrorText error={erase.error} className="text-small" />
    </>
  );
}

function Detail({ row, onClose }) {
  const detail = usePartyMember(row.id);
  const move = useMoveMember();
  const m = detail.data || row;
  const actions = m.erased_at ? [] : MOVES[m.status] || [];

  return (
    <Dialog title={m.full_name} description={placeOf(m)} onClose={onClose}>
      <div className="flex flex-col gap-1.5 text-ui text-muted-foreground">
        <div><Badge tone={STATUS_TONE[m.status]}>{STATUS_LABEL[m.status]}</Badge></div>
        <div>Phone: {m.phone}</div>
        <div>Email: {m.email || "—"}</div>
        <div>Applied: {formatDate(m.created_at)}</div>
        {detail.data && (
          <>
            <div>Decided: {formatDate(m.decided_at)}</div>
            {m.status_reason && <div>Reason: {m.status_reason}</div>}
            <div>Consent ({m.consent_channel}, {formatDate(m.consent_at)}): {m.consent_wording}</div>
          </>
        )}
      </div>
      <ErrorText error={detail.error} />
      <MoveButtons moves={actions} move={move} id={m.id} placeholder="Reason (optional)" />
      <ErrorText error={move.error} className="text-small" />
      {detail.data && <Erase member={m} />}
    </Dialog>
  );
}

export default function Members() {
  const { filters, set, offset, setOffset, list, items, total, exportCsv, exportError } =
    useRegister(usePartyMembers, { q: "", status: "", where: NO_PLACE }, exportPartyMembers);
  const [open, setOpen] = useState(null);
  const { linked, close: closeLinked } = useLinkedRecord(set("status"));

  if (list.isLoading) return <LoadingText />;
  if (list.error) return <ErrorText error={list.error} />;

  return (
    <>
      <SlottedHeader
        title="Members"
        sub={`${total} on the register`}
        actions={<Button shape="rounded" variant="quiet" onClick={exportCsv}>Export CSV</Button>}
      />
      <ErrorText error={exportError} />
      <div className="flex flex-wrap gap-2">
        <Input
          aria-label="Search members"
          className="w-auto flex-[2_1_240px]"
          placeholder="Search name, phone or email"
          value={filters.q}
          onChange={(e) => set("q")(e.target.value)}
        />
        <StatusFilter labels={STATUS_LABEL} value={filters.status} onChange={set("status")} />
        <PlaceCascade place={filters.where} onChange={set("where")} />
      </div>
      <Card variant="outline">
        <Table stack minWidth={720}>
          <THead><TR><TH>Name</TH><TH>Phone</TH><TH>Ward / constituency / county</TH><TH>Status</TH><TH>Applied</TH></TR></THead>
          <TBody>
            {items.map((m) => (
              <TR key={m.id}>
                <TD><RowButton onClick={() => setOpen(m)}>{m.full_name}</RowButton></TD>
                <TD className="text-muted-foreground">{m.phone}</TD>
                <TD className="text-muted-foreground">{placeOf(m)}</TD>
                <TD><Badge tone={STATUS_TONE[m.status]}>{STATUS_LABEL[m.status]}</Badge></TD>
                <TD className="text-muted-foreground">{formatDate(m.created_at)}</TD>
              </TR>
            ))}
            {items.length === 0 && <TR><TD colSpan={5} className="text-center text-muted-foreground">No members match.</TD></TR>}
          </TBody>
        </Table>
      </Card>
      <Pager offset={offset} size={PAGE_SIZE} shown={items.length} total={total} noun="members" onChange={setOffset} />
      {open && <Detail row={open} onClose={() => setOpen(null)} />}
      {linked && !open && <Linked id={linked} useRecord={usePartyMember} Detail={Detail} onClose={closeLinked} />}
    </>
  );
}
