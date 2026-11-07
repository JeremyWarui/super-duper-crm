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
} from "../../api/hooks";
import { Badge, Button, ErrorState, FormActions, LoadingState, Modal, Pager, PageTitle, Panel } from "../../components/ui";
import { MOVES, NO_PLACE, PAGE_SIZE, STATUS_LABEL, STATUS_TONE } from "./helpers";
import { formatDate } from "../../lib/format";
import PlaceFilters from "./PlaceFilters";

const place = (m) => [m.ward.name, m.constituency.name, m.county.name].join(" / ");
const ERASABLE = ["withdrawn", "rejected"];

function Erase({ member }) {
  const erase = useEraseMember();
  const [asking, setAsking] = useState(false);
  if (member.erased_at) return <div className="muted">Details erased on {formatDate(member.erased_at)}.</div>;
  if (!ERASABLE.includes(member.status)) return null;
  return (
    <>
      <FormActions>
        {asking ? (
          <>
            <span className="muted">Erase their name, phone, email and account for good?</span>
            <Button tone="danger" disabled={erase.isPending} onClick={() => erase.mutate(member.id)}>Yes, erase</Button>
            <Button onClick={() => setAsking(false)}>Cancel</Button>
          </>
        ) : (
          <Button tone="danger" onClick={() => setAsking(true)}>Erase their details</Button>
        )}
      </FormActions>
      {erase.isError && <div className="form-error">{erase.error.message}</div>}
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
    <Modal title={m.full_name} sub={place(m)} onClose={onClose}>
      <div className="modal-text">
        <div><Badge text={STATUS_LABEL[m.status]} tone={STATUS_TONE[m.status]} /></div>
        <div className="muted">Phone: {m.phone}</div>
        <div className="muted">Email: {m.email || "—"}</div>
        <div className="muted">Applied: {formatDate(m.created_at)}</div>
        {detail.data && (
          <>
            <div className="muted">Decided: {formatDate(m.decided_at)}</div>
            {m.status_reason && <div className="muted">Reason: {m.status_reason}</div>}
            <div className="muted">Consent ({m.consent_channel}, {formatDate(m.consent_at)}): {m.consent_wording}</div>
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
          <FormActions>
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
          </FormActions>
        </>
      )}
      {move.isError && <div className="form-error">{move.error.message}</div>}
      {detail.data && <Erase member={m} />}
    </Modal>
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
        <PlaceFilters place={where} onChange={set(setWhere)} />
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
                  <td className="muted">{formatDate(m.created_at)}</td>
                </tr>
              ))}
              {items.length === 0 && <tr><td colSpan={5} className="empty-row">No members match.</td></tr>}
            </tbody>
          </table>
        </div>
      </Panel>
      <Pager offset={offset} size={PAGE_SIZE} shown={items.length} total={total} noun="members" onChange={setOffset} />
      {open && <Detail row={open} onClose={() => setOpen(null)} />}
      {linked && !open && <Linked id={linked} onClose={closeLinked} />}
    </>
  );
}
