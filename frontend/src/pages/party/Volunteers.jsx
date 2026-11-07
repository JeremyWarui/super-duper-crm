// The membership officer's volunteer register: filter, page through, open a volunteer, set their
// status and notes, and erase a withdrawn volunteer's profile on request.
import { useState } from "react";
import {
  exportPartyVolunteers,
  useErasePartyVolunteer,
  usePartyVolunteers,
  useUpdateVolunteer,
} from "../../api/hooks";
import { Badge, Button, ErrorState, FormActions, LoadingState, Modal, Pager, PageTitle, Panel } from "../../components/ui";
import { AREA_LABEL, AREAS, CONTACT_LABEL, NO_PLACE, PAGE_SIZE, placeOf, PROFESSION_LABEL, STATUS_LABEL, STATUS_TONE, VOLUNTEER_STATUS_LABEL, VOLUNTEER_STATUS_TONE } from "./helpers";
import { formatDate } from "../../lib/format";
import PlaceFilters from "./PlaceFilters";

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
    <Modal title={v.full_name} sub={placeOf(v)} onClose={onClose}>
      <div className="modal-text">
        <div><Badge text={VOLUNTEER_STATUS_LABEL[v.status]} tone={VOLUNTEER_STATUS_TONE[v.status]} /></div>
        <div className="muted">Phone: {v.phone}</div>
        <div className="muted">Polling station: {v.registration_centre?.name || "Not given"}</div>
        <div className="muted">Profession: {professionOf(v)}</div>
        <div className="muted">Areas: {areasOf(v)}</div>
        <div className="muted">Preferred contact: {CONTACT_LABEL[v.preferred_contact] || v.preferred_contact}</div>
        <div className="muted">Membership: {STATUS_LABEL[v.member_status]}</div>
      </div>
      {v.erased_at ? (
        <div className="muted">Volunteer details erased on {formatDate(v.erased_at)}.</div>
      ) : (
        <>
          <textarea
            aria-label="Availability notes"
            className="app-field"
            placeholder="Availability notes"
            maxLength={2000}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
          <FormActions>
            <Button disabled={update.isPending} onClick={() => save({ availability_notes: notes.trim() || null })}>
              Save notes
            </Button>
            {canActivate && (
              <Button primary disabled={update.isPending} onClick={() => save({ status: "active" })}>Activate</Button>
            )}
            {v.status === "active" && (
              <Button disabled={update.isPending} onClick={() => save({ status: "inactive" })}>Deactivate</Button>
            )}
          </FormActions>
          {v.status === "withdrawn" && (
            <FormActions>
              {asking ? (
                <>
                  <span className="muted">Erase their volunteer details for good? Their membership stays.</span>
                  <Button tone="danger" disabled={erase.isPending} onClick={() => erase.mutate(v.id)}>Yes, erase</Button>
                  <Button onClick={() => setAsking(false)}>Cancel</Button>
                </>
              ) : (
                <Button tone="danger" onClick={() => setAsking(true)}>Erase volunteer details</Button>
              )}
            </FormActions>
          )}
        </>
      )}
      {update.isError && <div className="form-error">{update.error.message}</div>}
      {erase.isError && <div className="form-error">{erase.error.message}</div>}
    </Modal>
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

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;

  return (
    <>
      <PageTitle
        title="Volunteers"
        sub={`${total} on the register`}
        action={<Button onClick={exportCsv}>Export CSV</Button>}
      />
      {exportError && <ErrorState error={{ message: exportError }} />}
      <div className="flex flex-wrap gap-2 chip-row">
        <input
          aria-label="Search volunteers"
          className="app-field filter-field"
          placeholder="Search name or phone"
          value={q}
          onChange={(e) => set(setQ)(e.target.value)}
        />
        <select aria-label="Status" className="app-field filter-field" value={status} onChange={(e) => set(setStatus)(e.target.value)}>
          <option value="">All statuses</option>
          {Object.entries(VOLUNTEER_STATUS_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <select aria-label="Area" className="app-field filter-field" value={area} onChange={(e) => set(setArea)(e.target.value)}>
          <option value="">All areas</option>
          {AREAS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <PlaceFilters place={where} onChange={set(setWhere)} />
      </div>
      <Panel pad={0}>
        <div className="table-scroll">
          <table className="table">
            <thead><tr><th>Name</th><th>Phone</th><th>Ward / constituency / county</th><th>Status</th><th>Profession</th><th>Areas</th><th>Member</th><th>Contact</th></tr></thead>
            <tbody>
              {items.map((v) => (
                <tr key={v.id}>
                  <td className="strong"><button type="button" className="link-button" onClick={() => setOpenId(v.id)}>{v.full_name}</button></td>
                  <td className="muted">{v.phone}</td>
                  <td className="muted">{placeOf(v)}</td>
                  <td><Badge text={VOLUNTEER_STATUS_LABEL[v.status]} tone={VOLUNTEER_STATUS_TONE[v.status]} /></td>
                  <td className="muted">{professionOf(v)}</td>
                  <td className="muted">{areasOf(v)}</td>
                  <td><Badge text={STATUS_LABEL[v.member_status]} tone={STATUS_TONE[v.member_status]} /></td>
                  <td className="muted">{CONTACT_LABEL[v.preferred_contact] || v.preferred_contact}</td>
                </tr>
              ))}
              {items.length === 0 && <tr><td colSpan={8} className="empty-row">No volunteers match.</td></tr>}
            </tbody>
          </table>
        </div>
      </Panel>
      <Pager offset={offset} size={PAGE_SIZE} shown={items.length} total={total} noun="volunteers" onChange={setOffset} />
      {open && <Detail key={open.id} row={open} onClose={() => setOpenId(null)} />}
    </>
  );
}
