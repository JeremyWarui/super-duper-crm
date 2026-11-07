// The membership officer's volunteer register: filter, page through, open a volunteer, set their
// status and notes, and erase a withdrawn volunteer's profile on request.
import { useState } from "react";
import {
  exportPartyVolunteers,
  useErasePartyVolunteer,
  usePartyVolunteers,
  useUpdateVolunteer,
} from "@/api/hooks";
import { SlottedHeader } from "@/components/layout/AppPage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { ErrorText } from "@/components/ui/error-text";
import { FormActions } from "@/components/ui/form-actions";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { LoadingText } from "@/components/ui/loading-text";
import { Pager } from "@/components/ui/pager";
import { RowButton, TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { formatDate, placeOf } from "@/lib/format";
import { AREA_LABEL, AREAS, CONTACT_LABEL, NO_PLACE, PAGE_SIZE, PROFESSION_LABEL, STATUS_LABEL, STATUS_TONE, VOLUNTEER_STATUS_LABEL, VOLUNTEER_STATUS_TONE } from "./helpers";
import PlaceCascade from "@/components/PlaceCascade";

const areasOf = (v) =>
  v.interests.map((x) => (x === "other" && v.interest_other ? `Other: ${v.interest_other}` : AREA_LABEL[x] || x)).join(", ");
const professionOf = (v) =>
  v.profession === "other" ? v.profession_other : PROFESSION_LABEL[v.profession] || "Not given";

function Detail({ row, onClose }) {
  const update = useUpdateVolunteer();
  const erase = useErasePartyVolunteer();
  const [asking, setAsking] = useState(false);
  const [notes, setNotes] = useState(row.availability_notes || "");
  const v = erase.data || update.data || row;
  const canActivate = (v.status === "interested" || v.status === "inactive") && v.member_status === "approved";
  const save = (body) => update.mutate({ id: v.id, ...body });

  return (
    <Dialog title={v.full_name} description={placeOf(v)} onClose={onClose}>
      <div className="flex flex-col gap-1.5 text-ui text-muted-foreground">
        <div><Badge tone={VOLUNTEER_STATUS_TONE[v.status]}>{VOLUNTEER_STATUS_LABEL[v.status]}</Badge></div>
        <div>Phone: {v.phone}</div>
        <div>Polling station: {v.registration_centre?.name || "Not given"}</div>
        <div>Profession: {professionOf(v)}</div>
        <div>Areas: {areasOf(v)}</div>
        <div>Preferred contact: {CONTACT_LABEL[v.preferred_contact] || v.preferred_contact}</div>
        <div>Membership: {STATUS_LABEL[v.member_status]}</div>
      </div>
      {v.erased_at ? (
        <p className="text-ui text-muted-foreground">Volunteer details erased on {formatDate(v.erased_at)}.</p>
      ) : (
        <>
          <Textarea
            aria-label="Availability notes"
            placeholder="Availability notes"
            maxLength={2000}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
          <FormActions>
            <Button shape="rounded" variant="quiet" disabled={update.isPending} onClick={() => save({ availability_notes: notes.trim() || null })}>
              Save notes
            </Button>
            {canActivate && (
              <Button shape="rounded" disabled={update.isPending} onClick={() => save({ status: "active" })}>Activate</Button>
            )}
            {v.status === "active" && (
              <Button shape="rounded" variant="quiet" disabled={update.isPending} onClick={() => save({ status: "inactive" })}>Deactivate</Button>
            )}
          </FormActions>
          {v.status === "withdrawn" && (
            <FormActions>
              {asking ? (
                <>
                  <span className="text-ui text-muted-foreground">Erase their volunteer details for good? Their membership stays.</span>
                  <Button shape="rounded" variant="danger" disabled={erase.isPending} onClick={() => erase.mutate(v.id)}>Yes, erase</Button>
                  <Button shape="rounded" variant="quiet" onClick={() => setAsking(false)}>Cancel</Button>
                </>
              ) : (
                <Button shape="rounded" variant="danger" onClick={() => setAsking(true)}>Erase volunteer details</Button>
              )}
            </FormActions>
          )}
        </>
      )}
      <ErrorText error={update.error} className="text-small" />
      <ErrorText error={erase.error} className="text-small" />
    </Dialog>
  );
}

export default function Volunteers() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [area, setArea] = useState("");
  const [where, setWhere] = useState(NO_PLACE);
  const [offset, setOffset] = useState(0);
  const [openId, setOpenId] = useState(null);
  const [exportError, setExportError] = useState("");

  const filters = { q: q.trim(), status, area, ...where };
  const { data, isLoading, error } = usePartyVolunteers({ ...filters, limit: PAGE_SIZE, offset });
  const set = (setter) => (value) => { setter(value); setOffset(0); };
  const total = data?.total ?? 0;
  const items = data?.items || [];
  const open = items.find((v) => v.id === openId);

  const exportCsv = async () => {
    setExportError("");
    try {
      await exportPartyVolunteers(filters);
    } catch (e) {
      setExportError(e.message);
    }
  };

  if (isLoading) return <LoadingText />;
  if (error) return <ErrorText error={error} />;

  return (
    <>
      <SlottedHeader
        title="Volunteers"
        sub={`${total} on the register`}
        actions={<Button shape="rounded" variant="quiet" onClick={exportCsv}>Export CSV</Button>}
      />
      <ErrorText error={exportError} />
      <div className="grid grid-cols-[repeat(auto-fill,minmax(210px,1fr))] gap-2">
        <Input
          aria-label="Search volunteers"
          className="sm:col-span-2"
          placeholder="Search name or phone"
          value={q}
          onChange={(e) => set(setQ)(e.target.value)}
        />
        <NativeSelect aria-label="Status" className="w-auto min-w-0 flex-[1_1_180px]" value={status} onChange={(e) => set(setStatus)(e.target.value)}>
          <option value="">All statuses</option>
          {Object.entries(VOLUNTEER_STATUS_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </NativeSelect>
        <NativeSelect aria-label="Area" className="w-auto min-w-0 flex-[1_1_180px]" value={area} onChange={(e) => set(setArea)(e.target.value)}>
          <option value="">All areas</option>
          {AREAS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </NativeSelect>
        <PlaceCascade place={where} onChange={set(setWhere)} />
      </div>
      <Card variant="outline">
        <Table stack minWidth={960}>
          <THead><TR><TH>Name</TH><TH>Phone</TH><TH>Ward / constituency / county</TH><TH>Status</TH><TH>Profession</TH><TH>Areas</TH><TH>Member</TH><TH>Contact</TH></TR></THead>
          <TBody>
            {items.map((v) => (
              <TR key={v.id}>
                <TD><RowButton onClick={() => setOpenId(v.id)}>{v.full_name}</RowButton></TD>
                <TD className="text-muted-foreground">{v.phone}</TD>
                <TD className="text-muted-foreground">{placeOf(v)}</TD>
                <TD><Badge tone={VOLUNTEER_STATUS_TONE[v.status]}>{VOLUNTEER_STATUS_LABEL[v.status]}</Badge></TD>
                <TD className="text-muted-foreground">{professionOf(v)}</TD>
                <TD className="text-muted-foreground">{areasOf(v)}</TD>
                <TD><Badge tone={STATUS_TONE[v.member_status]}>{STATUS_LABEL[v.member_status]}</Badge></TD>
                <TD className="text-muted-foreground">{CONTACT_LABEL[v.preferred_contact] || v.preferred_contact}</TD>
              </TR>
            ))}
            {items.length === 0 && <TR><TD colSpan={8} className="text-center text-muted-foreground">No volunteers match.</TD></TR>}
          </TBody>
        </Table>
      </Card>
      <Pager offset={offset} size={PAGE_SIZE} shown={items.length} total={total} noun="volunteers" onChange={setOffset} />
      {open && <Detail key={open.id} row={open} onClose={() => setOpenId(null)} />}
    </>
  );
}
