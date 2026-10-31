// The membership officer's register: filter, page through, open a member, move their status.
import { useState } from "react";
import {
  exportPartyMembers,
  useMoveMember,
  usePartyMember,
  usePartyMembers,
  usePartyPlaces,
} from "../../api/hooks";
import { Badge, Button, ErrorState, LoadingState, Modal, PageTitle, Panel } from "../../components/ui";
import { MOVES, STATUS_LABEL, STATUS_TONE } from "./helpers";

const PAGE_SIZE = 50;

const place = (m) => [m.ward.name, m.constituency.name, m.county.name].join(" / ");
const day = (iso) => (iso ? new Date(iso).toLocaleDateString() : "—");

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
  const detail = usePartyMember(row.id);
  const move = useMoveMember();
  const [reason, setReason] = useState("");
  const m = detail.data || row;
  const actions = MOVES[m.status] || [];

  return (
    <Modal title={m.full_name} sub={place(m)} onClose={onClose}>
      <div className="modal-text">
        <div><Badge text={STATUS_LABEL[m.status]} tone={STATUS_TONE[m.status]} /></div>
        <div className="muted">Phone: {m.phone}</div>
        <div className="muted">Email: {m.email || "—"}</div>
        <div className="muted">Applied: {day(m.created_at)}</div>
        {detail.data && (
          <>
            <div className="muted">Decided: {day(m.decided_at)}</div>
            {m.status_reason && <div className="muted">Reason: {m.status_reason}</div>}
            <div className="muted">Consent ({m.consent_channel}, {day(m.consent_at)}): {m.consent_wording}</div>
          </>
        )}
      </div>
      {detail.error && <ErrorState error={detail.error} />}
      {actions.length > 0 && (
        <>
          <input
            aria-label="Reason"
            className="app-field"
            placeholder="Reason (optional)"
            maxLength={1000}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <div className="flex justify-end gap-2 form-actions">
            {actions.map(([status, label]) => (
              <Button
                key={status + label}
                primary={status === "approved"}
                disabled={move.isPending}
                onClick={() =>
                  move.mutate({ id: m.id, status, reason: reason.trim() }, { onSuccess: () => setReason("") })
                }
              >
                {label}
              </Button>
            ))}
          </div>
        </>
      )}
      {move.isError && <div className="form-error">{move.error.message}</div>}
    </Modal>
  );
}

export default function Members() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [county, setCounty] = useState("");
  const [constituency, setConstituency] = useState("");
  const [ward, setWard] = useState("");
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState(null);
  const [exportError, setExportError] = useState("");
  const counties = usePartyPlaces();
  const constituencies = usePartyPlaces({ county, enabled: !!county });
  const wards = usePartyPlaces({ constituency, enabled: !!constituency });

  const filters = { q: q.trim(), status, county, constituency, ward };
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

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;

  return (
    <>
      <PageTitle
        title="Members"
        sub={`${total} on the register`}
        action={<Button onClick={exportCsv}>Export CSV</Button>}
      />
      {exportError && <ErrorState error={{ message: exportError }} />}
      <div className="flex flex-wrap gap-2 chip-row">
        <input
          aria-label="Search members"
          className="app-field filter-field"
          placeholder="Search name, phone or email"
          value={q}
          onChange={(e) => set(setQ)(e.target.value)}
        />
        <select aria-label="Status" className="app-field filter-field" value={status} onChange={(e) => set(setStatus)(e.target.value)}>
          <option value="">All statuses</option>
          {Object.entries(STATUS_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <PlaceFilter label="County" value={county} places={counties.data} onChange={(v) => { set(setCounty)(v); setConstituency(""); setWard(""); }} />
        <PlaceFilter label="Constituency" value={constituency} places={constituencies.data} disabled={!county} onChange={(v) => { set(setConstituency)(v); setWard(""); }} />
        <PlaceFilter label="Ward" value={ward} places={wards.data} disabled={!constituency} onChange={set(setWard)} />
      </div>
      <Panel pad={0}>
        <div className="table-scroll">
          <table className="table">
            <thead><tr><th>Name</th><th>Phone</th><th>Ward / constituency / county</th><th>Status</th><th>Applied</th></tr></thead>
            <tbody>
              {items.map((m) => (
                <tr key={m.id}>
                  <td className="strong"><button type="button" className="link-button" onClick={() => setOpen(m)}>{m.full_name}</button></td>
                  <td className="muted">{m.phone}</td>
                  <td className="muted">{place(m)}</td>
                  <td><Badge text={STATUS_LABEL[m.status]} tone={STATUS_TONE[m.status]} /></td>
                  <td className="muted">{day(m.created_at)}</td>
                </tr>
              ))}
              {items.length === 0 && <tr><td colSpan={5} className="empty-row">No members match.</td></tr>}
            </tbody>
          </table>
        </div>
      </Panel>
      <div className="flex items-center justify-between gap-2 chip-row">
        <span className="meta">
          {total === 0 ? "0 members" : `${offset + 1}–${offset + items.length} of ${total}`}
        </span>
        <div className="flex gap-2">
          <Button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Previous</Button>
          <Button disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>Next</Button>
        </div>
      </div>
      {open && <Detail row={open} onClose={() => setOpen(null)} />}
    </>
  );
}
