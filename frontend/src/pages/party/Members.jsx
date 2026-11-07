// The membership officer's register: filter, page through, open a member, move their status, and
// erase a withdrawn or rejected member's details on request.
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
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
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { ErrorText } from "@/components/ui/error-text";
import { FormActions } from "@/components/ui/form-actions";
import { Input, NativeSelect } from "@/components/ui/input";
import { LoadingText } from "@/components/ui/loading-text";
import { Pager } from "@/components/ui/pager";
import { RowButton, TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { formatDate } from "@/lib/format";
import { MOVES, NO_PLACE, PAGE_SIZE, placeOf, STATUS_LABEL, STATUS_TONE } from "./helpers";
import PlaceFilters from "./PlaceFilters";

const ERASABLE = ["withdrawn", "rejected"];

function Erase({ member }) {
  const erase = useEraseMember();
  const [asking, setAsking] = useState(false);
  if (member.erased_at) return <p className="text-ui text-muted-foreground">Details erased on {formatDate(member.erased_at)}.</p>;
  if (!ERASABLE.includes(member.status)) return null;
  return (
    <>
      <FormActions>
        {asking ? (
          <>
            <span className="text-ui text-muted-foreground">Erase their name, phone, email and account for good?</span>
            <Button shape="rounded" variant="danger" disabled={erase.isPending} onClick={() => erase.mutate(member.id)}>Yes, erase</Button>
            <Button shape="rounded" variant="quiet" onClick={() => setAsking(false)}>Cancel</Button>
          </>
        ) : (
          <Button shape="rounded" variant="danger" onClick={() => setAsking(true)}>Erase their details</Button>
        )}
      </FormActions>
      <ErrorText error={erase.error} className="text-small" />
    </>
  );
}

function Detail({ row, onClose }) {
  const detail = usePartyMember(row.id);
  const move = useMoveMember();
  const [reason, setReason] = useState("");
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
      {actions.length > 0 && (
        <>
          <Input
            aria-label="Reason"
            placeholder="Reason (optional)"
            maxLength={1000}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <FormActions>
            {actions.map(([status, label]) => (
              <Button
                key={status + label}
                shape="rounded"
                variant={status === "approved" ? "primary" : "quiet"}
                disabled={move.isPending}
                onClick={() =>
                  move.mutate({ id: m.id, status, reason: reason.trim() }, { onSuccess: () => setReason("") })
                }
              >
                {label}
              </Button>
            ))}
          </FormActions>
        </>
      )}
      <ErrorText error={move.error} className="text-small" />
      {detail.data && <Erase member={m} />}
    </Dialog>
  );
}

// A record opened from a link (`?open=<id>`), once it has loaded.
function Linked({ id, onClose }) {
  const detail = usePartyMember(id);
  return detail.data ? <Detail row={detail.data} onClose={onClose} /> : null;
}

export default function Members() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [where, setWhere] = useState(NO_PLACE);
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState(null);
  const [exportError, setExportError] = useState("");
  const [params, setParams] = useSearchParams();
  const linked = params.get("open");
  const closeLinked = () => setParams((p) => { p.delete("open"); return p; }, { replace: true });
  // A link's `?status=` sets the filter each time the link changes.
  const wanted = params.get("status");
  const [applied, setApplied] = useState(null);
  if (wanted !== null && wanted !== applied) {
    setApplied(wanted);
    setStatus(wanted);
    setOffset(0);
  }

  const filters = { q: q.trim(), status, ...where };
  const { data, isLoading, error } = usePartyMembers({ ...filters, limit: PAGE_SIZE, offset });
  const set = (setter) => (value) => { setter(value); setOffset(0); };
  const total = data?.total ?? 0;
  const items = data?.items || [];

  const exportCsv = async () => {
    setExportError("");
    try {
      await exportPartyMembers(filters);
    } catch (e) {
      setExportError(e.message);
    }
  };

  if (isLoading) return <LoadingText />;
  if (error) return <ErrorText error={error} />;

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
          value={q}
          onChange={(e) => set(setQ)(e.target.value)}
        />
        <NativeSelect aria-label="Status" className="w-auto min-w-0 flex-[1_1_180px]" value={status} onChange={(e) => set(setStatus)(e.target.value)}>
          <option value="">All statuses</option>
          {Object.entries(STATUS_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </NativeSelect>
        <PlaceFilters place={where} onChange={set(setWhere)} />
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
      {linked && !open && <Linked id={linked} onClose={closeLinked} />}
    </>
  );
}
