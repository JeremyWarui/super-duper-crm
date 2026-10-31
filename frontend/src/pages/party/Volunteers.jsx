// The membership officer's volunteer register: filter, page through, open a volunteer, set their status and notes.
import { useState } from "react";
import {
  exportPartyVolunteers,
  usePartyPlaces,
  usePartyVolunteers,
  useUpdateVolunteer,
} from "../../api/hooks";
import { Badge, Button, ErrorState, LoadingState, Modal, PageTitle, Panel } from "../../components/ui";
import {
  CONTACT_LABEL,
  INTERESTS,
  INTEREST_LABEL,
  STATUS_LABEL,
  STATUS_TONE,
  VOLUNTEER_STATUS_LABEL,
  VOLUNTEER_STATUS_TONE,
} from "./helpers";

const PAGE_SIZE = 50;

const place = (v) => [v.ward.name, v.constituency.name, v.county.name].join(" / ");
const interestsOf = (v) => v.interests.map((x) => INTEREST_LABEL[x] || x).join(", ");

function PlaceFilter({ label, value, onChange, places, disabled }) {
  return (
    <select
      aria-label={label}
      className="app-field filter-field"
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">All {label.toLowerCase()}s</option>
      {(places || []).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
    </select>
  );
}

function Detail({ row, onClose }) {
  const update = useUpdateVolunteer();
  const [notes, setNotes] = useState(row.availability_notes || "");
  const v = update.data || row;
  const canActivate = (v.status === "interested" || v.status === "inactive") && v.member_status === "approved";
  const save = (body) => update.mutate({ id: v.id, ...body });

  return (
    <Modal title={v.full_name} sub={place(v)} onClose={onClose}>
      <div className="modal-text">
        <div><Badge text={VOLUNTEER_STATUS_LABEL[v.status]} tone={VOLUNTEER_STATUS_TONE[v.status]} /></div>
        <div className="muted">Phone: {v.phone}</div>
        <div className="muted">Interests: {interestsOf(v)}</div>
        <div className="muted">Preferred contact: {CONTACT_LABEL[v.preferred_contact] || v.preferred_contact}</div>
        <div className="muted">Membership: {STATUS_LABEL[v.member_status]}</div>
      </div>
      <textarea
        aria-label="Availability notes"
        className="app-field"
        placeholder="Availability notes"
        maxLength={2000}
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
      />
      <div className="flex justify-end gap-2 form-actions">
        <Button disabled={update.isPending} onClick={() => save({ availability_notes: notes.trim() || null })}>
          Save notes
        </Button>
        {canActivate && (
          <Button primary disabled={update.isPending} onClick={() => save({ status: "active" })}>Activate</Button>
        )}
        {v.status === "active" && (
          <Button disabled={update.isPending} onClick={() => save({ status: "inactive" })}>Deactivate</Button>
        )}
      </div>
      {update.isError && <div className="form-error">{update.error.message}</div>}
    </Modal>
  );
}

export default function Volunteers() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [interest, setInterest] = useState("");
  const [county, setCounty] = useState("");
  const [constituency, setConstituency] = useState("");
  const [ward, setWard] = useState("");
  const [offset, setOffset] = useState(0);
  const [openId, setOpenId] = useState(null);
  const [exportError, setExportError] = useState("");
  const counties = usePartyPlaces();
  const constituencies = usePartyPlaces({ county, enabled: !!county });
  const wards = usePartyPlaces({ constituency, enabled: !!constituency });

  const filters = { q: q.trim(), status, interest, county, constituency, ward };
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
        <select aria-label="Interest" className="app-field filter-field" value={interest} onChange={(e) => set(setInterest)(e.target.value)}>
          <option value="">All interests</option>
          {INTERESTS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <PlaceFilter label="County" value={county} places={counties.data} onChange={(v) => { set(setCounty)(v); setConstituency(""); setWard(""); }} />
        <PlaceFilter label="Constituency" value={constituency} places={constituencies.data} disabled={!county} onChange={(v) => { set(setConstituency)(v); setWard(""); }} />
        <PlaceFilter label="Ward" value={ward} places={wards.data} disabled={!constituency} onChange={set(setWard)} />
      </div>
      <Panel pad={0}>
        <div className="table-scroll">
          <table className="table">
            <thead><tr><th>Name</th><th>Phone</th><th>Ward / constituency / county</th><th>Status</th><th>Interests</th><th>Member</th><th>Contact</th></tr></thead>
            <tbody>
              {items.map((v) => (
                <tr key={v.id}>
                  <td className="strong"><button type="button" className="link-button" onClick={() => setOpenId(v.id)}>{v.full_name}</button></td>
                  <td className="muted">{v.phone}</td>
                  <td className="muted">{place(v)}</td>
                  <td><Badge text={VOLUNTEER_STATUS_LABEL[v.status]} tone={VOLUNTEER_STATUS_TONE[v.status]} /></td>
                  <td className="muted">{interestsOf(v)}</td>
                  <td><Badge text={STATUS_LABEL[v.member_status]} tone={STATUS_TONE[v.member_status]} /></td>
                  <td className="muted">{CONTACT_LABEL[v.preferred_contact] || v.preferred_contact}</td>
                </tr>
              ))}
              {items.length === 0 && <tr><td colSpan={7} className="empty-row">No volunteers match.</td></tr>}
            </tbody>
          </table>
        </div>
      </Panel>
      <div className="flex items-center justify-between gap-2 chip-row">
        <span className="meta">
          {total === 0 ? "0 volunteers" : `${offset + 1}–${offset + items.length} of ${total}`}
        </span>
        <div className="flex gap-2">
          <Button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Previous</Button>
          <Button disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>Next</Button>
        </div>
      </div>
      {open && <Detail key={open.id} row={open} onClose={() => setOpenId(null)} />}
    </>
  );
}
