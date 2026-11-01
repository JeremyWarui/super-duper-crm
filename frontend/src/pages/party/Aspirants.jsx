// The nominations officer's page: nominate approved members, move nominations, create workspaces.
import { useState } from "react";
import {
  useAspirant,
  useAspirants,
  useCandidates,
  useCreateWorkspace,
  useMoveAspirant,
  useNominate,
  usePartyPlaces,
} from "../../api/hooks";
import {
  Badge,
  Button,
  ErrorState,
  LoadingState,
  Modal,
  PageTitle,
  Panel,
  PasswordModal,
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
          <Button onClick={() => setMember(null)}>Choose someone else</Button>
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
              <button key={c.id} type="button" className="link-button" onClick={() => setMember(c)}>
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
  const [form, setForm] = useState({ title: "", election_date: "", candidate: "", manager: "" });
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  const submit = () =>
    create.mutate(
      {
        id: aspirant.id,
        candidate: { username: form.candidate.trim() },
        ...(form.manager.trim() ? { manager: { username: form.manager.trim() } } : {}),
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
      <input aria-label="Manager's username" className="app-field" maxLength={150}
        placeholder="A manager's new username (optional)" value={form.manager} onChange={set("manager")} />
      {create.isError && <div className="form-error">{create.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Button primary disabled={form.candidate.trim().length < 3 || create.isPending} onClick={submit}>
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
      <PasswordModal
        title={`Login for ${first.username}`}
        password={first.password}
        onClose={() => setLogins(rest.length ? rest : null)}
      >
        {first.role === "candidate" ? "The aspirant's login." : "The campaign manager's login."}
      </PasswordModal>
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

export default function Aspirants() {
  const [status, setStatus] = useState("");
  const [seat, setSeat] = useState("");
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState(null);
  const [nominating, setNominating] = useState(false);
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
    </>
  );
}
