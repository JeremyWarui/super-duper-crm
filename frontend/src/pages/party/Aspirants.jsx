// The nominations officer's page: nominate approved members, move nominations, create workspaces.
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { isEmail } from "../../lib/email";
import { useAuth } from "../../store/auth";
import {
  useAspirant,
  useAspirants,
  useCandidates,
  useCreateWorkspace,
  useDraftNominationWindow,
  useMarkNominationFeePaid,
  useMoveAspirant,
  useNominate,
  useNominationWindows,
  usePartyPlaces,
  usePublishNominationWindow,
  useReviseNominationWindow,
} from "../../api/hooks";
import {
  Badge,
  Button,
  ErrorState,
  LoadingState,
  Modal,
  PageTitle,
  Panel,
  InviteModal,
} from "../../components/ui";
import {
  ASPIRANT_MOVES,
  ASPIRANT_STATUS_LABEL,
  ASPIRANT_STATUS_TONE,
  NEEDS_REASON,
  SEAT_AREA,
  SEAT_LABEL,
  SEATS,
} from "./helpers";

const PAGE_SIZE = 50;
const day = (iso) => (iso ? new Date(iso).toLocaleDateString() : "—");

function Select({ label, value, onChange, options, disabled, blank }) {
  return (
    <select
      aria-label={label}
      className="app-field filter-field"
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">{blank}</option>
      {(options || []).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
    </select>
  );
}

// County, then constituency, then ward, down to the level the seat is fought over.
function AreaPicker({ level, area, setArea }) {
  const counties = usePartyPlaces();
  const constituencies = usePartyPlaces({ county: area.county, enabled: !!area.county });
  const wards = usePartyPlaces({ constituency: area.constituency, enabled: !!area.constituency });
  return (
    <div className="flex flex-wrap gap-2 chip-row">
      <Select
        label="County"
        blank="Pick the county"
        value={area.county}
        options={counties.data}
        onChange={(county) => setArea({ county, constituency: "", ward: "" })}
      />
      {level !== "county" && (
        <Select
          label="Constituency"
          blank="Pick the constituency"
          value={area.constituency}
          options={constituencies.data}
          disabled={!area.county}
          onChange={(constituency) => setArea({ ...area, constituency, ward: "" })}
        />
      )}
      {level === "ward" && (
        <Select
          label="Ward"
          blank="Pick the ward"
          value={area.ward}
          options={wards.data}
          disabled={!area.constituency}
          onChange={(ward) => setArea({ ...area, ward })}
        />
      )}
    </div>
  );
}

function Nominate({ onClose }) {
  const [q, setQ] = useState("");
  const [member, setMember] = useState(null);
  const [seat, setSeat] = useState("mca");
  const [area, setArea] = useState({ county: "", constituency: "", ward: "" });
  const candidates = useCandidates(q);
  const nominate = useNominate();
  const level = SEAT_AREA[seat];
  const ready = member && area[level];

  const submit = () =>
    nominate.mutate(
      { member: member.id, seat, [level]: area[level] },
      { onSuccess: onClose },
    );

  return (
    <Modal title="Nominate a member" sub="Only approved members without a live nomination are offered." onClose={onClose}>
      {member ? (
        <div className="modal-text">
          <div className="strong">{member.full_name}</div>
          <div className="muted">{member.ward.name}</div>
          <Button onClick={() => { setMember(null); nominate.reset(); }}>Choose someone else</Button>
        </div>
      ) : (
        <>
          <input
            aria-label="Find a member"
            className="app-field"
            placeholder="Name, or their whole phone number"
            maxLength={100}
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          {candidates.error && <ErrorState error={candidates.error} />}
          <div className="modal-text">
            {(candidates.data || []).map((c) => (
              <button key={c.id} type="button" className="link-button" onClick={() => { setMember(c); nominate.reset(); }}>
                {c.full_name} · {c.ward.name}
              </button>
            ))}
            {candidates.isSuccess && candidates.data.length === 0 && (
              <div className="muted">No approved member matches.</div>
            )}
          </div>
        </>
      )}
      <select
        aria-label="Seat"
        className="app-field"
        value={seat}
        onChange={(e) => { setSeat(e.target.value); setArea({ county: "", constituency: "", ward: "" }); }}
      >
        {SEATS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
      <AreaPicker level={level} area={area} setArea={setArea} />
      {nominate.isError && <div className="form-error">{nominate.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Button onClick={onClose}>Cancel</Button>
        <Button primary disabled={!ready || nominate.isPending} onClick={submit}>
          {nominate.isPending ? "Nominating…" : "Nominate"}
        </Button>
      </div>
    </Modal>
  );
}

function Workspace({ aspirant, onDone }) {
  const create = useCreateWorkspace();
  const [form, setForm] = useState({ title: "", election_date: "", candidate: "", candidate_email: "", manager: "", manager_email: "" });
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  const submit = () =>
    create.mutate(
      {
        id: aspirant.id,
        candidate: { username: form.candidate.trim(), email: form.candidate_email.trim() },
        ...(form.manager.trim() ? { manager: { username: form.manager.trim(), email: form.manager_email.trim() } } : {}),
        ...(form.title.trim() ? { title: form.title.trim() } : {}),
        ...(form.election_date ? { election_date: form.election_date } : {}),
      },
      { onSuccess: (made) => onDone(made.logins) },
    );

  return (
    <div className="modal-text">
      <div className="strong">Create the campaign workspace</div>
      <div className="muted">
        It is built on the {SEAT_LABEL[aspirant.seat]} seat for {aspirant.area.name}.
      </div>
      <input aria-label="Campaign title" className="app-field" maxLength={150}
        placeholder={`${aspirant.member.full_name} for ${SEAT_LABEL[aspirant.seat]}`}
        value={form.title} onChange={set("title")} />
      <input aria-label="Election date" type="date" className="app-field"
        value={form.election_date} onChange={set("election_date")} />
      <input aria-label="Aspirant's username" className="app-field" maxLength={150}
        placeholder="The aspirant's new username" value={form.candidate} onChange={set("candidate")} />
      <input aria-label="Aspirant's email" type="email" className="app-field" maxLength={254}
        placeholder="The aspirant's email, to sign in with" value={form.candidate_email} onChange={set("candidate_email")} />
      <input aria-label="Manager's username" className="app-field" maxLength={150}
        placeholder="A manager's new username (optional)" value={form.manager} onChange={set("manager")} />
      {form.manager.trim() ? (
        <input aria-label="Manager's email" type="email" className="app-field" maxLength={254}
          placeholder="The manager's email, to sign in with" value={form.manager_email} onChange={set("manager_email")} />
      ) : null}
      {create.isError && <div className="form-error">{create.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Button primary disabled={form.candidate.trim().length < 3 || !isEmail(form.candidate_email) || (form.manager.trim() && !isEmail(form.manager_email)) || create.isPending} onClick={submit}>
          {create.isPending ? "Creating…" : "Create workspace"}
        </Button>
      </div>
    </div>
  );
}

function Detail({ row, onClose }) {
  const detail = useAspirant(row.id);
  const move = useMoveAspirant();
  const [reason, setReason] = useState("");
  const [logins, setLogins] = useState(null);
  const a = detail.data || row;
  const actions = ASPIRANT_MOVES[a.status] || [];

  if (logins?.length) {
    const [first, ...rest] = logins;
    return (
      <InviteModal
        title={first.role === "candidate" ? "The aspirant's login" : "The campaign manager's login"}
        invite={first.invite}
        username={first.username}
        onClose={() => setLogins(rest.length ? rest : null)}
      />
    );
  }

  return (
    <Modal title={a.member.full_name} sub={`${SEAT_LABEL[a.seat]} · ${a.area.name}`} onClose={onClose}>
      <div className="modal-text">
        <div><Badge text={ASPIRANT_STATUS_LABEL[a.status]} tone={ASPIRANT_STATUS_TONE[a.status]} /></div>
        <div className="muted">Nominated: {day(a.created_at)}</div>
        <div className="muted">Decided: {day(a.decided_at)}</div>
        {a.status_reason && <div className="muted">Reason: {a.status_reason}</div>}
        <div className="muted">Workspace: {a.campaign_id ? "created" : "none yet"}</div>
      </div>
      {a.window_title && <Application a={a} />}
      {detail.error && <ErrorState error={detail.error} />}
      {actions.length > 0 && (
        <>
          <input
            aria-label="Reason"
            className="app-field"
            placeholder="Reason (needed to reject or suspend)"
            maxLength={1000}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <div className="flex justify-end gap-2 form-actions">
            {actions.map(([status, label]) => (
              <Button
                key={status + label}
                primary={status === "approved"}
                disabled={move.isPending || (NEEDS_REASON.has(status) && !reason.trim())}
                onClick={() =>
                  move.mutate({ id: a.id, status, reason: reason.trim() }, { onSuccess: () => setReason("") })
                }
              >
                {label}
              </Button>
            ))}
          </div>
        </>
      )}
      {move.isError && <div className="form-error">{move.error.message}</div>}
      {a.status === "approved" && !a.campaign_id && <Workspace aspirant={a} onDone={setLogins} />}
    </Modal>
  );
}

// A member's own application: what they declared, attached and paid, for vetting.
function Application({ a }) {
  const pay = useMarkNominationFeePaid();
  const [reference, setReference] = useState("");
  return (
    <div className="modal-text" aria-label="Application">
      <div className="muted">Applied in: {a.window_title}</div>
      <div className="muted">Declaration: {a.declared_at ? `signed ${day(a.declared_at)}` : "not yet"}</div>
      <div className="muted">
        Fee: {a.fee_kes ? `KES ${a.fee_kes.toLocaleString("en-KE")} · ${a.fee_paid_at ? `paid, ref ${a.fee_reference}` : "not paid"}` : "none"}
      </div>
      <div className="muted">Documents: {a.documents.length === 0 ? "none" : ""}</div>
      {a.documents.map((d) => (
        <a key={d.id} href={`/api/party/nominations/applications/${a.id}/documents/${d.id}/`} target="_blank" rel="noreferrer">{d.label}</a>
      ))}
      {a.fee_kes > 0 && !a.fee_paid_at && a.status === "draft" && (
        <div className="flex gap-2">
          <input aria-label="Fee reference" className="app-field" placeholder="M-Pesa or bank reference" maxLength={50} value={reference} onChange={(e) => setReference(e.target.value)} />
          <Button disabled={pay.isPending || reference.trim().length < 3} onClick={() => pay.mutate({ id: a.id, reference: reference.trim() })}>Mark fee paid</Button>
        </div>
      )}
      {pay.isError && <div className="form-error">{pay.error.message}</div>}
    </div>
  );
}

// The nominations timetable: the officer drafts it, the Super Admin (not the drafter) publishes it.
function Timetable() {
  const windows = useNominationWindows();
  const publish = usePublishNominationWindow();
  const superuser = useAuth((st) => st.user?.is_superuser);
  const [editing, setEditing] = useState(null);
  if (windows.isLoading) return null;
  if (windows.error) return <ErrorState error={windows.error} />;
  return (
    <Panel>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="strong">Nominations timetable</div>
        <Button onClick={() => setEditing({})}>Draft a timetable</Button>
      </div>
      <div className="modal-text" aria-label="Timetables">
        {windows.data.length === 0 && <div className="muted">No timetable yet. Members can apply only inside a published one.</div>}
        {windows.data.map((w) => (
          <div key={w.id} className="flex flex-wrap items-center gap-2">
            <span className="strong">{w.title}</span>
            <span className="muted">{day(w.opens_on)} – {day(w.closes_on)}</span>
            <span className="muted">{w.seats.map((x) => `${SEAT_LABEL[x.seat]} ${x.fee_kes ? `KES ${x.fee_kes.toLocaleString("en-KE")}` : "no fee"}`).join(" · ")}</span>
            <Badge text={w.status === "published" ? "Published" : "Draft"} tone={w.status === "published" ? "ok" : "warn"} />
            {w.status === "draft" && <Button onClick={() => setEditing(w)}>Edit</Button>}
            {w.status === "draft" && superuser && !w.mine && (
              <Button primary disabled={publish.isPending} onClick={() => publish.mutate(w.id)}>Publish</Button>
            )}
            {w.status === "draft" && w.mine && <span className="muted">Someone else publishes it.</span>}
          </div>
        ))}
      </div>
      {publish.isError && <div className="form-error">{publish.error.message}</div>}
      {editing && <TimetableForm window={editing} onClose={() => setEditing(null)} />}
    </Panel>
  );
}

function TimetableForm({ window: w, onClose }) {
  const draft = useDraftNominationWindow();
  const revise = useReviseNominationWindow();
  const save = w.id ? revise : draft;
  const fees = Object.fromEntries((w.seats || []).map((x) => [x.seat, String(x.fee_kes)]));
  const [form, setForm] = useState({ title: w.title || "", opens_on: w.opens_on || "", closes_on: w.closes_on || "", requirements: w.requirements || "" });
  const [seats, setSeats] = useState(fees);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const chosen = Object.entries(seats).map(([seat, fee]) => ({ seat, fee_kes: Number(fee) || 0 }));
  const ready = form.title.trim() && form.opens_on && form.closes_on && form.closes_on >= form.opens_on && chosen.length > 0;
  const submit = () => {
    const body = { ...form, seats: chosen };
    save.mutate(w.id ? { id: w.id, body } : body, { onSuccess: onClose });
  };
  return (
    <Modal title={w.id ? "Edit timetable" : "Draft a timetable"} sub="A draft stays private until the Super Admin publishes it." onClose={onClose}>
      <input aria-label="Title" className="app-field" placeholder="e.g. Nominations 2027" maxLength={150} value={form.title} onChange={set("title")} />
      <div className="flex flex-wrap gap-2">
        <label className="muted">Opens <input aria-label="Opens" type="date" className="app-field" value={form.opens_on} onChange={set("opens_on")} /></label>
        <label className="muted">Closes <input aria-label="Closes" type="date" className="app-field" value={form.closes_on} onChange={set("closes_on")} /></label>
      </div>
      <fieldset className="modal-text">
        <legend className="strong">Seats and nomination fees (KES)</legend>
        {SEATS.map(([value, label]) => (
          <div key={value} className="flex items-center gap-2">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={value in seats}
                onChange={(e) => { const next = { ...seats }; if (e.target.checked) next[value] = "0"; else delete next[value]; setSeats(next); }} />
              {label}
            </label>
            {value in seats && (
              <input aria-label={`${label} fee`} type="number" min={0} className="app-field" value={seats[value]}
                onChange={(e) => setSeats({ ...seats, [value]: e.target.value })} />
            )}
          </div>
        ))}
      </fieldset>
      <textarea aria-label="Requirements" className="app-field" rows={4} maxLength={5000} placeholder="Requirements aspirants must meet" value={form.requirements} onChange={set("requirements")} />
      {save.isError && <div className="form-error">{save.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Button onClick={onClose}>Cancel</Button>
        <Button primary disabled={!ready || save.isPending} onClick={submit}>{save.isPending ? "Saving…" : "Save draft"}</Button>
      </div>
    </Modal>
  );
}

// A record opened from a link (`?open=<id>`), once it has loaded.
function Linked({ id, onClose }) {
  const detail = useAspirant(id);
  return detail.data ? <Detail row={detail.data} onClose={onClose} /> : null;
}

export default function Aspirants() {
  const [status, setStatus] = useState("");
  const [seat, setSeat] = useState("");
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState(null);
  const [nominating, setNominating] = useState(false);
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
  const { data, isLoading, error } = useAspirants({ status, seat, limit: PAGE_SIZE, offset });
  const total = data?.total ?? 0;
  const items = data?.items || [];

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;

  return (
    <>
      <PageTitle
        title="Aspirants"
        sub={`${total} nominations`}
        action={<Button primary onClick={() => setNominating(true)}>Nominate a member</Button>}
      />
      <Timetable />
      <div className="flex flex-wrap gap-2 chip-row">
        <select aria-label="Status" className="app-field filter-field" value={status}
          onChange={(e) => { setStatus(e.target.value); setOffset(0); }}>
          <option value="">All statuses</option>
          {Object.entries(ASPIRANT_STATUS_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <select aria-label="Seat filter" className="app-field filter-field" value={seat}
          onChange={(e) => { setSeat(e.target.value); setOffset(0); }}>
          <option value="">All seats</option>
          {SEATS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </div>
      <Panel pad={0}>
        <div className="table-scroll">
          <table className="table">
            <thead><tr><th>Name</th><th>Seat</th><th>Area</th><th>Status</th><th>Workspace</th></tr></thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.id}>
                  <td className="strong"><button type="button" className="link-button" onClick={() => setOpen(a)}>{a.member.full_name}</button></td>
                  <td className="muted">{SEAT_LABEL[a.seat]}</td>
                  <td className="muted">{a.area.name}</td>
                  <td><Badge text={ASPIRANT_STATUS_LABEL[a.status]} tone={ASPIRANT_STATUS_TONE[a.status]} /></td>
                  <td className="muted">{a.campaign_id ? "Created" : "—"}</td>
                </tr>
              ))}
              {items.length === 0 && <tr><td colSpan={5} className="empty-row">No nominations match.</td></tr>}
            </tbody>
          </table>
        </div>
      </Panel>
      <div className="flex items-center justify-between gap-2 chip-row">
        <span className="meta">
          {total === 0 ? "0 nominations" : `${offset + 1}–${offset + items.length} of ${total}`}
        </span>
        <div className="flex gap-2">
          <Button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Previous</Button>
          <Button disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>Next</Button>
        </div>
      </div>
      {nominating && <Nominate onClose={() => setNominating(false)} />}
      {open && <Detail row={open} onClose={() => setOpen(null)} />}
      {linked && !open && <Linked id={linked} onClose={closeLinked} />}
    </>
  );
}
