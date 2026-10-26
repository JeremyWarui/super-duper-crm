// src/App.jsx  — the live-wired campaign dashboard.
// Role comes from the logged-in user; every page reads React Query hooks; the
// forms fire real mutations. Every class it uses is defined in index.css.
import React, { useState, useMemo, useRef, useEffect, useCallback } from "react";
import { QRCodeSVG } from "qrcode.react";
import { useAuth } from "./store/auth";
import { winNumber } from "./winNumber";
import { formatNumber as fmt } from "./lib/format";
import {
  Button,
  ErrorState,
  FieldLabel,
  LoadingState,
  Panel,
} from "./components/ui";
import {
  useCampaigns, useStrategy, useTargets, useEvents, useMobilizers, useSupporters,
  useScheduleEvent, useRecordEvent, useAddMobilizer, useRegisterSupporter, useUpdateTarget,
  useInviteToEvent, useCreateUser, useUpdateMobilizer, useTeam, useSetManager, useResetTeamPassword,
  usePayments, useSchedulePayment, useMarkPaid, useCancelPayment, usePayoutMode, useReleasePayment, useMarkNotSent, useSetSignups, useCentres, usePlaceSupporter, useCampaignSignups, useSetCampaignSignups,
} from "./api/hooks";

// ---- status helper (server gives progress; we colour it) ------------------
// A tone is one of good, warn, bad or neutral; index.css colours each.
function statusOf(progress) {
  if (progress >= 1) return { label: "Target met", tone: "good" };
  if (progress >= 0.6) return { label: "Building", tone: "warn" };
  return { label: "Behind", tone: "bad" };
}

// ---- shared UI ------------------------------------------------------------
const Badge = ({ text, tone = "neutral" }) => <span className={`badge tone-${tone}`}>{text}</span>;
const Bar = ({ pct, tone }) => <div className="bar"><div className={`bar-fill tone-${tone}`} style={{width: `${Math.min(pct, 100)}%`}} /></div>;
// A pill that toggles, for sort orders and filters.
const Chip = ({ on, onClick, className = "", children }) => <button type="button" aria-pressed={on} onClick={onClick} className={`chip ${on ? "chip-on" : ""} ${className}`.trim()}>{children}</button>;
const Card = Panel;
const Label = FieldLabel;
const Btn = Button;
const PrimaryBtn = ({ children, onClick, disabled }) => <Button primary onClick={onClick} disabled={disabled}>{children}</Button>;
const PageTitle = ({ title, sub, action }) => <div className="flex flex-wrap items-end justify-between gap-3 page-head"><div><div className="page-title">{title}</div>{sub && <div className="page-sub">{sub}</div>}</div>{action}</div>;
const Loading = LoadingState;
const ErrorMsg = ErrorState;

const Modal = ({ title, sub, onClose, locked, children }) => (
  <div onClick={locked ? undefined : onClose} className="modal-backdrop">
    <div onClick={(e) => e.stopPropagation()} className="modal">
      <div className="flex items-start justify-between modal-head">
        <div><div className="modal-title">{title}</div>{sub && <div className="modal-sub">{sub}</div>}</div>
        <button onClick={onClose} className="modal-close">×</button>
      </div>
      <div className="modal-body">{children}</div>
    </div>
  </div>
);

// A password shown once; a click on the backdrop leaves it open.
const PasswordModal = ({ title, password, onClose, children }) => (
  <Modal title={title} sub="Write the password down now. It is shown once." onClose={onClose} locked>
    <div className="modal-text">{children}</div>
    <div className="secret-box">
      <div className="meta">Password</div>
      <div className="secret-value">{password}</div>
    </div>
    <div className="flex justify-end gap-2 form-actions"><PrimaryBtn onClick={onClose}>Done</PrimaryBtn></div>
  </Modal>
);

// ---- dashboard blocks (fed by the /strategy/ endpoint) --------------------
function TallyHero({ s }) {
  const crossed = s.committed >= s.win_number;
  const cast = s.total_cast || s.win_number * 2;
  const tone = crossed ? "good" : "warn";
  return (
    <>
      <Card pad={20} className={`hero ${crossed ? "hero-crossed" : ""}`.trim()}>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div className="eyebrow">VOTES TO WIN THE SEAT</div>
          <div className="hero-meta">{s.units.length} units · {fmt(cast)} projected votes cast</div>
        </div>
        <div className="flex flex-wrap items-end gap-6 hero-figures">
          <span className="hero-number">{fmt(s.win_number)}</span>
          <div className="hero-progress">
            <div className={`hero-committed text-${tone}`}>{fmt(s.committed)} committed</div>
            <div className="hero-meta">{s.progress_pct}% there · {fmt(Math.max(s.win_number - s.committed, 0))} to go</div>
          </div>
        </div>
        <div className="winbar">
          <div className="winbar-track" />
          <div className={`winbar-fill tone-${tone}`} style={{width: `${(s.committed / cast) * 100}%`}} />
          <div className="winbar-line" style={{left: `${(s.win_number / cast) * 100}%`}} />
          <div className="winbar-label" style={{left: `${(s.win_number / cast) * 100}%`}}>WIN LINE</div>
        </div>
      </Card>
      <div className="kpi-grid">
        {[["Registered voters", fmt(s.total_registered)], ["Units covered", `${s.units.filter((u) => u.events > 0).length} / ${s.units.length}`],
          ["Mobilizers", `${s.units.filter((u) => u.has_mobilizer).length} / ${s.units.length}`], ["Units behind", String(s.units.filter((u) => u.progress < 0.6).length)]].map(([k, v]) => (
          <Card key={k} pad={20} className="kpi"><div className="kpi-label">{k}</div><div className="kpi-value">{v}</div></Card>
        ))}
      </div>
    </>
  );
}

// The mobilizer on a unit: its ward, or its registration centre in a ward race.
const holderOf = (mobilizers, unit) =>
  mobilizers.find((m) => m.ward === unit.ward && (m.registration_centre ?? null) === (unit.registration_centre ?? null));

function UnitRegister({ units, mobilizers = [], onAssign }) {
  const [sortKey, setSortKey] = useState("opportunity");
  const sorted = useMemo(() => {
    const a = [...units];
    if (sortKey === "opportunity") a.sort((x, y) => y.gap - x.gap);
    else if (sortKey === "needed") a.sort((x, y) => y.needed - x.needed);
    else a.sort((x, y) => x.progress - y.progress);
    return a;
  }, [units, sortKey]);
  return (
    <Card pad={0}>
      <div className="flex flex-wrap items-center justify-between gap-2 card-head">
        <div className="card-title">Targeting</div>
        <div className="flex gap-1 segmented">
          {[["opportunity", "Biggest gap"], ["needed", "Win number"], ["progress", "Least progress"]].map(([k, l]) => (
            <button key={k} type="button" aria-pressed={sortKey === k} onClick={() => setSortKey(k)} className={`segmented-option ${sortKey === k ? "segmented-option-on" : ""}`.trim()}>{l}</button>
          ))}
        </div>
      </div>
      <div className="table-scroll">
        <table className="table">
          <thead><tr>
            <th>Unit</th>
            <th className="num">Need</th>
            <th>Progress</th>
            <th className="center">Events</th>
            <th>Mobilizer</th>
          </tr></thead>
          <tbody>
            {sorted.map((u) => {
              const st = statusOf(u.progress);
              return (
                <tr key={u.unit}>
                  <td><div className="strong">{u.unit}</div><div className="cell-badge"><Badge text={st.label} tone={st.tone} /></div></td>
                  <td className="num figure">{fmt(u.needed)}</td>
                  <td className="progress-cell"><Bar pct={u.progress * 100} tone={st.tone} /><div className="cell-meta">{fmt(u.committed)} · {Math.round(u.progress * 100)}%</div></td>
                  <td className={`center figure ${u.events === 0 ? "text-bad" : ""}`.trim()}>{u.events}</td>
                  <td><MobilizerCell holder={holderOf(mobilizers, u)} onAssign={onAssign && ((holder) => onAssign(u, holder))} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function MobilizerCell({ holder, onAssign }) {
  if (holder) {
    return <div className="flex items-center gap-2"><span className="strong">{holder.full_name}</span>{onAssign && <Btn onClick={() => onAssign(holder)}>Change</Btn>}</div>;
  }
  return onAssign ? <Btn onClick={() => onAssign(null)}>Assign</Btn> : <span className="text-bad">None</span>;
}

const StrategyPanel = ({ notes }) => (
  <Card pad={20} className="strategy">
    <div className="card-title">Strategy read</div>
    <div className="card-sub">Computed from your targets, events and mobilizers.</div>
    <div className="notes">
      {(notes || []).map((n, i) => (
        <div key={i} className={`note tone-${n.tone === "go" ? "good" : "warn"}`}>
          <div className="note-title">{n.title}</div>
          <div className="note-text">{n.text}</div>
        </div>
      ))}
      {(!notes || notes.length === 0) && <div className="muted">No flags right now — coverage looks balanced.</div>}
    </div>
  </Card>
);

// ---- forms (fire mutations) ----------------------------------------------
// Units (wards, or centres in a ward race) with no mobilizer, plus the one `keep` holds.
const freeUnits = (units, mobilizers, keep) =>
  units.filter((u) => { const h = holderOf(mobilizers, u); return !h || h.id === keep?.id; });

// Adds a mobilizer, or edits one when `mobilizer` is given; the unit is optional.
function MobilizerForm({ campaignId, units, byCentre, mobilizers, mobilizer, onClose }) {
  const add = useAddMobilizer();
  const update = useUpdateMobilizer();
  const createUser = useCreateUser();
  const [name, setName] = useState(mobilizer?.full_name || ""); const [phone, setPhone] = useState(mobilizer?.phone || "");
  const [picked, setPicked] = useState(null);  // null until the user changes the ward box
  const unitKey = picked ?? (units.find((u) => mobilizer && holderOf([mobilizer], u))?.key || "");
  const [withLogin, setWithLogin] = useState(false);
  const [username, setUsername] = useState("");
  const [made, setMade] = useState(null);
  const busy = add.isPending || update.isPending || createUser.isPending;
  const error = add.error || update.error || createUser.error;
  const ok = name.trim() && (!withLogin || username.trim().length >= 3);
  const choices = freeUnits(units, mobilizers, mobilizer);
  const unitWord = byCentre ? "centre" : "ward";

  const save = () => {
    const [first, ...rest] = name.trim().split(/\s+/);
    const unit = units.find((u) => u.key === unitKey);
    const place = { ward: unit?.ward ?? null, registration_centre: unit?.registration_centre ?? null };
    if (mobilizer) {
      const moved = picked !== null;
      update.mutate({ id: mobilizer.id, full_name: name.trim(), phone: phone.trim(), ...(moved && place) }, { onSuccess: onClose });
    } else if (withLogin) {
      createUser.mutate(
        { username: username.trim().toLowerCase(), role: "mobilizer", first_name: first, last_name: rest.join(" "), phone: phone.trim(), campaign: campaignId, ...place },
        { onSuccess: (created) => setMade({ ...created, place: unit?.name }) },
      );
    } else {
      add.mutate({ campaign: campaignId, ...place, full_name: name.trim(), phone: phone.trim() }, { onSuccess: onClose });
    }
  };

  if (made) {
    return (
      <PasswordModal title="Mobilizer added" password={made.password} onClose={onClose}>
        <b>{made.username}</b> can now sign in{made.place ? <> and work {made.place}.</> : <>. Assign them a {unitWord} from the Overview.</>}
      </PasswordModal>
    );
  }

  return (
    <Modal title={mobilizer ? "Edit mobilizer" : "Add mobilizer"} sub={`One mobilizer per ${unitWord}. The ${unitWord} can be left for later.`} onClose={onClose}>
      <Label>Full name</Label><input className="app-field" value={name} onChange={(e) => setName(e.target.value)} />
      <div className="field-gap" /><Label>Phone</Label><input className="app-field" value={phone} onChange={(e) => setPhone(e.target.value)} />
      <div className="field-gap" /><Label>{byCentre ? "Registration centre" : "Ward"}</Label>
      <select aria-label={byCentre ? "Registration centre" : "Ward"} className="app-field" value={unitKey} onChange={(e) => setPicked(e.target.value)}>
        <option value="">No {unitWord} yet</option>
        {choices.map((u) => <option key={u.key} value={u.key}>{u.name}</option>)}
      </select>
      {!mobilizer && (
        <label className="flex items-start gap-2 checkbox-row">
          <input type="checkbox" checked={withLogin} onChange={(e) => setWithLogin(e.target.checked)} className="checkbox" />
          Give them a login, so they can record their own events and supporters.
        </label>
      )}
      {withLogin && (
        <>
          <div className="field-gap" /><Label>Username</Label>
          <input className="app-field" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="juma" />
        </>
      )}
      {error && <div className="form-error">{error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Btn onClick={onClose}>Cancel</Btn>
        <PrimaryBtn disabled={!ok || busy} onClick={save}>{busy ? "Saving…" : "Save mobilizer"}</PrimaryBtn>
      </div>
    </Modal>
  );
}

// Puts an unassigned mobilizer on the clicked unit; the unit comes from the row.
function AssignMobilizerForm({ unit, holder, mobilizers, onClose }) {
  const update = useUpdateMobilizer();
  const free = mobilizers.filter((m) => !m.ward);
  const unitWord = unit.registration_centre ? "centre" : "ward";
  const [picked, setPicked] = useState("");
  const chosen = picked || free[0]?.id || "";
  const assign = () => update.mutate({ id: chosen, ward: unit.ward, registration_centre: unit.registration_centre ?? null }, { onSuccess: onClose });
  const remove = () => update.mutate({ id: holder.id, ward: null, registration_centre: null }, { onSuccess: onClose });

  return (
    <Modal title={`Mobilizer for ${unit.unit}`} sub={holder ? `Now: ${holder.full_name}` : `Pick a mobilizer without a ${unitWord}.`} onClose={onClose}>
      {free.length > 0 ? (
        <>
          <Label>Mobilizer</Label>
          <select aria-label="Mobilizer" className="app-field" value={chosen} onChange={(e) => setPicked(e.target.value)}>
            {free.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}
          </select>
        </>
      ) : (
        <div className="muted">Every mobilizer already has a {unitWord}. Add one on the Mobilizers page.</div>
      )}
      {update.error && <div className="form-error">{update.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        {holder && <Btn onClick={remove} disabled={update.isPending}>Remove {holder.full_name}</Btn>}
        <Btn onClick={onClose}>Cancel</Btn>
        <PrimaryBtn disabled={!chosen || update.isPending} onClick={assign}>{update.isPending ? "Saving…" : "Assign"}</PrimaryBtn>
      </div>
    </Modal>
  );
}

// In an MCA race an event is held at one registration centre, which its sign-ups count toward.
function ScheduleEventForm({ campaignId, wardOptions, byCentre, onClose }) {
  const schedule = useScheduleEvent();
  const [title, setTitle] = useState(""); const [venue, setVenue] = useState(""); const [date, setDate] = useState("");
  const [ward, setWard] = useState(wardOptions[0]?.id || "");
  const [centre, setCentre] = useState("");
  const centresQuery = useCentres(byCentre ? ward : null);
  const centres = centresQuery.data || [];
  const ok = title.trim() && ward && date && !centresQuery.isFetching && (!byCentre || !centres.length || centre);
  return (
    <Modal title="Schedule event" sub="Attendance is recorded after it happens." onClose={onClose}>
      <Label>Event title</Label><input className="app-field" value={title} onChange={(e) => setTitle(e.target.value)} />
      <div className="field-gap" /><Label>Ward</Label>
      <select className="app-field" value={ward} onChange={(e) => { setWard(e.target.value); setCentre(""); }}>{wardOptions.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select>
      {byCentre && centres.length > 0 && (
        <>
          <div className="field-gap" /><Label>Registration centre</Label>
          <select aria-label="Registration centre" className="app-field" value={centre} onChange={(e) => setCentre(e.target.value)}>
            <option value="">Pick the centre</option>
            {centres.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </>
      )}
      <div className="field-gap" /><Label>Venue</Label><input className="app-field" value={venue} onChange={(e) => setVenue(e.target.value)} />
      <div className="field-gap" /><Label>Date</Label><input type="date" className="app-field" value={date} onChange={(e) => setDate(e.target.value)} />
      {schedule.isError && <div className="form-error">{schedule.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Btn onClick={onClose}>Cancel</Btn>
        <PrimaryBtn disabled={!ok || schedule.isPending} onClick={() => schedule.mutate({ campaign: campaignId, ward, registration_centre: centre || null, title: title.trim(), venue: venue.trim(), scheduled_date: date, status: "planned" }, { onSuccess: onClose })}>{schedule.isPending ? "Saving…" : "Schedule event"}</PrimaryBtn>
      </div>
    </Modal>
  );
}

function RecordForm({ event, onClose }) {
  const record = useRecordEvent();
  const [reached, setReached] = useState(""); const [attended, setAttended] = useState("");
  const r = Number(reached), a = Number(attended);
  const ok = reached !== "" && attended !== "" && r > 0 && a <= r;
  return (
    <Modal title="Record attendance" sub={`${event.title} · ${event.ward_name}`} onClose={onClose}>
      <Label>How many were reached / invited</Label><input type="number" className="app-field" value={reached} onChange={(e) => setReached(e.target.value)} />
      <div className="field-gap" /><Label>How many attended</Label><input type="number" className="app-field" value={attended} onChange={(e) => setAttended(e.target.value)} />
      {reached !== "" && attended !== "" && a > r && <div className="form-error">Attendance can't exceed those reached.</div>}
      {record.isError && <div className="form-error">{record.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Btn onClick={onClose}>Cancel</Btn>
        <PrimaryBtn disabled={!ok || record.isPending} onClick={() => record.mutate({ id: event.id, number_reached: r, number_attended: a }, { onSuccess: onClose })}>{record.isPending ? "Saving…" : "Save & mark done"}</PrimaryBtn>
      </div>
    </Modal>
  );
}


const LEVELS = [["supporter", "Supporters"], ["undecided", "Undecided"], ["opposed", "Opposed"]];
const SMS_PART = 160;

function InviteForm({ event, onClose }) {
  const invite = useInviteToEvent();
  const [message, setMessage] = useState(`${event.title}${event.venue ? ` at ${event.venue}` : ""}. Come through.`);
  const [levels, setLevels] = useState(["supporter", "undecided"]);
  const [wholeCampaign, setWholeCampaign] = useState(false);
  const [result, setResult] = useState(null);

  const parts = message.length === 0 ? 0 : Math.floor((message.length - 1) / SMS_PART) + 1;
  const ok = message.trim().length > 0 && !invite.isPending;
  const toggle = (key) => setLevels((L) => (L.includes(key) ? L.filter((k) => k !== key) : [...L, key]));
  const send = (dry) =>
    invite.mutate(
      { id: event.id, message: message.trim(), support_levels: levels, whole_campaign: wholeCampaign, dry_run: dry },
      { onSuccess: setResult },
    );

  return (
    <Modal title="Invite supporters" sub={`${event.title} · ${wholeCampaign ? "whole campaign" : event.ward_name}`} onClose={onClose}>
      <Label>Message</Label>
      <textarea className="textarea app-field" value={message} onChange={(e) => { setMessage(e.target.value); setResult(null); }} />
      <div className="field-hint">{message.length} characters · {parts} SMS part{parts === 1 ? "" : "s"} per person</div>

      <div className="field-gap" /><Label>Send to</Label>
      <div className="flex flex-wrap gap-1 chip-row">
        {LEVELS.map(([key, label]) => (
          <Chip key={key} on={levels.includes(key)} onClick={() => { toggle(key); setResult(null); }}>{label}</Chip>
        ))}
      </div>
      <label className="flex items-start gap-2 checkbox-row">
        <input type="checkbox" checked={wholeCampaign} onChange={(e) => { setWholeCampaign(e.target.checked); setResult(null); }} className="checkbox" />
        Everyone on the campaign, not just {event.ward_name}
      </label>

      {result && <InviteResult result={result} />}
      {invite.isError && <div className="form-error">{invite.error.message}</div>}

      <div className="flex justify-end gap-2 form-actions">
        <Btn onClick={onClose}>Close</Btn>
        <Btn onClick={() => send(true)} disabled={!ok}>{invite.isPending ? "Working…" : "Preview"}</Btn>
        <PrimaryBtn disabled={!ok} onClick={() => send(false)}>{invite.isPending ? "Sending…" : "Send"}</PrimaryBtn>
      </div>
    </Modal>
  );
}

function InviteResult({ result }) {
  const tone = result.delivered ? "good" : "warn";
  return (
    <div className={`result tone-${tone}`}>
      <div className="result-title">
        {result.dry_run ? "Preview" : result.delivered ? "Sent" : "Not sent"}
        <span className="inline-badge"><Badge text={result.provider} tone={tone} /></span>
      </div>
      <div className="result-text">
        {fmt(result.supporters_matched)} supporter{result.supporters_matched === 1 ? "" : "s"} matched ·
        {" "}{fmt(result.requested)} usable number{result.requested === 1 ? "" : "s"} ·
        {" "}{result.parts} part{result.parts === 1 ? "" : "s"} each
      </div>
      {result.rejected.length > 0 && (
        <div className="result-bad">
          {result.rejected.length} number{result.rejected.length === 1 ? "" : "s"} unusable: {result.rejected.slice(0, 4).map((r) => r.phone || "(blank)").join(", ")}
        </div>
      )}
      {result.detail && <div className="result-note">{result.detail}</div>}
      {!result.dry_run && result.delivered && <div className="result-good">Reached is now {fmt(result.number_reached)}.</div>}
    </div>
  );
}

// ---- events + supporters lists -------------------------------------------
function EventList({ events, showActions, onRecord, onInvite, onQr }) {
  return (
    <Card pad={0}><div className="table-scroll">
      <table className="table">
        <thead><tr>
          <th>Event</th><th>Ward</th>
          <th>Date</th><th>Status</th>
          <th className="num">Reached</th><th className="num">Attended</th>
          <th className="num">Turnout</th>
          <th className="num">Signed up</th>
          {showActions && <th className="num">Invite</th>}
          {onQr && <th className="num">Sign-up</th>}
        </tr></thead>
        <tbody>
          {events.map((e) => {
            const done = e.status === "done";
            return (
              <tr key={e.id}>
                <td className="strong">{e.title}<div className="cell-sub">{e.venue || "—"}</div></td>
                <td>{e.ward_name}</td>
                <td>{e.scheduled_date ? new Date(e.scheduled_date).toLocaleDateString("en-GB", { day: "numeric", month: "short" }) : "—"}</td>
                <td><Badge text={done ? "Done" : "Planned"} tone={done ? "good" : "warn"} /></td>
                <td className="num">{done ? fmt(e.number_reached) : (showActions ? <Btn onClick={() => onRecord(e)}>Record</Btn> : "—")}</td>
                <td className="num">{done ? fmt(e.number_attended) : "—"}</td>
                <td className="num">{done ? `${e.turnout_pct}%` : "—"}</td>
                <td className="num">{fmt(e.signups)}{e.number_attended > 0 && <span className="muted"> ({Math.round((e.signups / e.number_attended) * 100)}%)</span>}</td>
                {showActions && <td className="actions-cell"><Btn onClick={() => onInvite(e)}>Invite</Btn></td>}
                {onQr && <td className="actions-cell">{e.signup_code && <Btn onClick={() => onQr(e)}>{e.signups_open ? "Sign-up QR" : "Closed"}</Btn>}</td>}
              </tr>
            );
          })}
          {events.length === 0 && <tr><td colSpan={10} className="empty-row">No events yet.</td></tr>}
        </tbody>
      </table>
    </div></Card>
  );
}

// An event's sign-up QR code and link, to print or show at the rally.
// Copy a sign-up link, or send it on WhatsApp with a line saying what it is for.
function ShareLink({ link, message }) {
  const [copied, setCopied] = useState(null);  // null until tried, then true or false
  const copy = () => (navigator.clipboard ? navigator.clipboard.writeText(link) : Promise.reject()).then(() => setCopied(true), () => setCopied(false));
  const whatsapp = `https://wa.me/?text=${encodeURIComponent(`${message} ${link}`)}`;
  return (
    <div className="flex flex-wrap gap-2 share-row">
      <Btn onClick={copy}>{copied ? "Copied" : "Copy link"}</Btn>
      <a href={whatsapp} target="_blank" rel="noreferrer" className="ui-button ui-button-outline">Share on WhatsApp</a>
      {copied === false && <span className="field-hint share-hint">This browser blocked copying; select the link above instead.</span>}
    </div>
  );
}

// The campaign-wide sign-up link for posters and messages; the manager opens and closes it.
function CampaignLinkModal({ campaign, onClose }) {
  const signups = useCampaignSignups(campaign.id);
  const setSignups = useSetCampaignSignups();
  const sub = "People open it, pick where they vote, and sign up as supporters.";
  if (signups.isLoading) return <Modal title="Campaign sign-up link" sub={sub} onClose={onClose}><Loading /></Modal>;
  if (signups.error) return <Modal title="Campaign sign-up link" sub={sub} onClose={onClose}><ErrorMsg error={signups.error} /></Modal>;
  const { code, open } = signups.data;
  const link = `${window.location.origin}/join/${code}`;
  return (
    <Modal title="Campaign sign-up link" sub={sub} onClose={onClose}>
      <div className="qr-print">
        <div className="qr-title">{campaign.title}</div>
        <QRCodeSVG value={link} size={220} marginSize={2} title={`Sign-up link for ${campaign.title}`} />
        <div className="qr-link">{link}</div>
      </div>
      {open
        ? <ShareLink link={link} message={`Sign up to support ${campaign.title}:`} />
        : <div className="field-hint share-row">The link is closed: anyone who opens it sees a "closed" page. Open it to start taking sign-ups.</div>}
      {setSignups.error && <ErrorMsg error={setSignups.error} />}
      <div className="flex justify-end gap-2 form-actions">
        <Btn onClick={() => setSignups.mutate({ campaign: campaign.id, open: !open })} disabled={setSignups.isPending}>{open ? "Close sign-ups" : "Open sign-ups"}</Btn>
        <Btn onClick={() => window.print()}>Print</Btn>
        <PrimaryBtn onClick={onClose}>Done</PrimaryBtn>
      </div>
    </Modal>
  );
}

function QrModal({ event, canClose, onClose }) {
  const setSignups = useSetSignups();
  const link = `${window.location.origin}/join/${event.signup_code}`;
  const [open, setOpen] = useState(event.signups_open);
  const toggle = () => setSignups.mutate({ id: event.id, open: !open }, { onSuccess: () => setOpen(!open) });
  return (
    <Modal title="Sign-up QR" sub={`${event.title || event.ward_name}: people scan it to sign up as supporters.`} onClose={onClose}>
      <div className="qr-print">
        <div className="qr-title">{event.title || event.ward_name}</div>
        <QRCodeSVG value={link} size={220} marginSize={2} title={`Sign-up link for ${event.title || event.ward_name}`} />
        <div className="qr-link">{link}</div>
      </div>
      {open && <ShareLink link={link} message={`Sign up as a supporter at ${event.title || event.ward_name}:`} />}
      {!open && <div className="form-error">Sign-ups are closed: the code shows a "closed" page.</div>}
      {setSignups.error && <div className="form-error">{setSignups.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        {canClose && <Btn onClick={toggle} disabled={setSignups.isPending}>{open ? "Close sign-ups" : "Reopen sign-ups"}</Btn>}
        <Btn onClick={() => window.print()}>Print</Btn>
        <PrimaryBtn onClick={onClose}>Done</PrimaryBtn>
      </div>
    </Modal>
  );
}

function SupportersView({ campaignId, centreWard, share }) {
  const [sharing, setSharing] = useState(false);
  const { data, isLoading, error } = useSupporters(campaignId);
  const targetsQuery = useTargets(campaignId);
  const targeted = new Set((targetsQuery.data || []).map((t) => t.registration_centre));
  const showCentre = centreWard && targetsQuery.isSuccess;
  const allCentres = useCentres(centreWard).data || [];
  const centres = allCentres.filter((c) => targeted.has(c.id));
  const place = usePlaceSupporter();
  const [filter, setFilter] = useState("all");
  if (isLoading) return <Loading />; if (error) return <ErrorMsg error={error} />;
  const all = data || [];
  const shown = filter === "all" ? all : all.filter((s) => s.support_level === filter);
  const toneOf = { supporter: "good", undecided: "warn", opposed: "bad" };
  return (
    <>
      <PageTitle title="Supporters" sub={`${all.length} on the register`} action={share ? <Btn primary onClick={() => setSharing(true)}>Sign-up link</Btn> : null} />
      <div className="flex gap-1 chip-row">
        {["all", "supporter", "undecided", "opposed"].map((f) => <Chip key={f} on={filter === f} onClick={() => setFilter(f)} className="chip-capitalize">{f}</Chip>)}
      </div>
      <Card pad={0}><div className="table-scroll">
        <table className="table">
          <thead><tr><th>Name</th><th>Phone</th><th>Support</th>{showCentre && <th>Centre</th>}<th>Consent</th></tr></thead>
          <tbody>{shown.map((s) => (<tr key={s.id}><td className="strong">{s.full_name}</td><td className="muted">{s.phone}</td><td><Badge text={s.support_level} tone={toneOf[s.support_level]} /></td>{showCentre && <td>{targeted.has(s.registration_centre)
            ? allCentres.find((c) => c.id === s.registration_centre)?.name || "—"
            : <select aria-label={`Centre for ${s.full_name}`} className="inline-select app-field" value="" disabled={place.isPending} onChange={(e) => place.mutate({ id: s.id, registration_centre: e.target.value })}><option value="">{s.registration_centre ? `${allCentres.find((c) => c.id === s.registration_centre)?.name || "Centre"} has no target` : "Needs a centre"}</option>{centres.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>}</td>}<td>{s.consent_given ? <span className="text-good">✓</span> : <span className="text-bad">missing</span>}</td></tr>))}
          {place.isError && <tr><td colSpan={5} className="form-error">{place.error.message}</td></tr>}
          {shown.length === 0 && <tr><td colSpan={5} className="empty-row">None yet.</td></tr>}</tbody>
        </table>
      </div></Card>
      {sharing && <CampaignLinkModal campaign={share} onClose={() => setSharing(false)} />}
    </>
  );
}

const SAVE_STATUS = {
  saving: ["Saving…", "muted"],
  saved: ["Saved", "text-good"],
  failed: ["Not saved, try again", "text-bad"],
};

// A slider moves the screen at once and saves only when the user lets go.
function TargetRow({ target, draft, onDraft, onSettle }) {
  const { mutate } = useUpdateTarget();
  const [status, setStatus] = useState("");
  const slider = useRef(null);
  const saved = Math.round(target.projected_turnout_pct || 60);
  const pct = draft ?? saved;
  const needed = draft == null ? target.votes_needed : winNumber(target.registered_voters, draft);
  const known = useRef(saved);  // the value saved or on its way; a release with it sends nothing
  useEffect(() => { if (status !== "saving") known.current = saved; }, [status, saved]);

  // Saves on release or a key press, not on every move.
  // "change" alone is not enough: Chromium skips it when a drag ends where it started.
  useEffect(() => {
    const el = slider.current;
    const save = () => {
      const value = Number(el.value);
      if (value === known.current) return;
      known.current = value;
      setStatus("saving");
      mutate(
        { id: target.id, projected_turnout_pct: value },
        {
          onSuccess: () => { setStatus("saved"); onSettle(target.id, value, false); },
          onError: () => { setStatus("failed"); onSettle(target.id, value, true); },
        },
      );
    };
    el.addEventListener("change", save);
    el.addEventListener("pointerup", save);
    return () => {
      el.removeEventListener("change", save);
      el.removeEventListener("pointerup", save);
    };
  }, [target.id, mutate, onSettle]);

  return (
    <tr>
      <td className="strong">{target.centre_name || target.ward_name}</td>
      <td className="num">{fmt(target.registered_voters)}</td>
      <td className="center">
        <input ref={slider} type="range" min={40} max={85} value={pct} aria-label={`Turnout for ${target.centre_name || target.ward_name}`} onChange={(e) => { onDraft(target.id, Number(e.target.value)); setStatus((s) => (s === "saving" ? s : "")); }} className="slider" />
        <span className="slider-value">{pct}%</span>
        {status && !(status === "saved" && draft != null) && <div className={`save-status ${SAVE_STATUS[status][1]}`}>{SAVE_STATUS[status][0]}</div>}
      </td>
      <td className="num figure">{fmt(needed)}</td>
    </tr>
  );
}

function TargetsView({ campaignId }) {
  const { data, isLoading, error } = useTargets(campaignId);
  const [drafts, setDrafts] = useState({});  // turnout per target id, until its save settles
  const onDraft = useCallback((id, pct) => setDrafts((d) => ({ ...d, [id]: pct })), []);
  // A failed save always puts the saved number back; a good one keeps a newer drag.
  const onSettle = useCallback((id, pct, failed) => setDrafts((d) => {
    if (!failed && d[id] !== pct) return d;
    const { [id]: _settled, ...rest } = d;
    return rest;
  }), []);
  if (isLoading) return <Loading />; if (error) return <ErrorMsg error={error} />;
  const rows = data || [];
  const total = rows.reduce((s, t) => s + ((t.id in drafts ? winNumber(t.registered_voters, drafts[t.id]) : t.votes_needed) || 0), 0);
  return (
    <>
      <PageTitle title="Targets — the win number" sub="Set projected turnout per unit; the win number recomputes on the server." />
      <Card pad={0}><div className="table-scroll">
        <table className="table">
          <thead><tr><th>Unit</th><th className="num">Registered</th><th className="center">Turnout %</th><th className="num">Votes needed</th></tr></thead>
          <tbody>{rows.map((t) => <TargetRow key={t.id} target={t} draft={drafts[t.id]} onDraft={onDraft} onSettle={onSettle} />)}</tbody>
          <tfoot><tr className="total-row"><td className="total-label"  colSpan={3}>TOTAL WIN NUMBER</td><td className="num total-value">{fmt(total)}</td></tr></tfoot>
        </table>
      </div></Card>
      <div className="page-note">Release a slider to save — the server recomputes the win number and the dashboard updates.</div>
    </>
  );
}

function MobilizersView({ campaignId, units, byCentre, onAdd, onEdit }) {
  const { data, isLoading, error } = useMobilizers(campaignId);
  if (isLoading) return <Loading />; if (error) return <ErrorMsg error={error} />;
  const placeOf = (m) => {
    if (!byCentre) return m.ward_name;
    if (!m.registration_centre) return null;
    return units.find((u) => u.registration_centre === m.registration_centre)?.name || "A centre with no target";
  };
  return (
    <>
      <PageTitle title="Mobilizers" sub={`Ground organisers by ${byCentre ? "registration centre" : "ward"}.`} action={<Btn primary onClick={onAdd}>Add mobilizer</Btn>} />
      <Card pad={0}><div className="table-scroll">
        <table className="table">
          <thead><tr><th>Name</th><th>{byCentre ? "Centre" : "Ward"}</th><th>Phone</th><th/></tr></thead>
          <tbody>{(data || []).map((m) => (<tr key={m.id}><td className="strong">{m.full_name}</td><td className={placeOf(m) ? undefined : "muted"}>{placeOf(m) || `No ${byCentre ? "centre" : "ward"} yet`}</td><td className="muted">{m.phone || "—"}</td><td className="actions-cell"><Btn onClick={() => onEdit(m)}>Edit</Btn></td></tr>))}
          {(!data || data.length === 0) && <tr><td colSpan={4} className="empty-row">No mobilizers yet.</td></tr>}</tbody>
        </table>
      </div></Card>
    </>
  );
}

// In an MCA race the supporter is filed to a registration centre with a target, the mobilizer's own to start.
function RegisterSupporterForm({ campaignId, wardOptions, byCentre }) {
  const reg = useRegisterSupporter();
  const user = useAuth((s) => s.user);
  const own = (useMobilizers(campaignId).data || []).find((m) => m.user === user?.id);
  const [form, setForm] = useState({ full_name: "", phone: "", ward: "", support_level: "supporter", consent_given: false });
  const ward = form.ward || wardOptions[0]?.id || "";
  const [picked, setPicked] = useState(null);  // null until the centre box is changed
  const centresQuery = useCentres(byCentre ? ward : null);
  const targetsQuery = useTargets(campaignId);
  const targeted = new Set((targetsQuery.data || []).map((t) => t.registration_centre));
  const centres = (centresQuery.data || []).filter((c) => targeted.has(c.id));
  const ownCentre = own?.ward === ward && targeted.has(own?.registration_centre) ? own.registration_centre : null;
  const centre = picked ?? ownCentre ?? "";
  const loaded = !centresQuery.isFetching && !centresQuery.isError && targetsQuery.isSuccess;
  const ok = form.full_name.trim() && form.consent_given && ward && (!byCentre || (loaded && centre));
  if (reg.isSuccess) return <Card pad={20}><div className="success-title">Registered.</div><div className="form-actions"><Btn onClick={() => reg.reset()}>Register another</Btn></div></Card>;
  return (
    <Card pad={20}>
      <Label>Full name</Label><input className="app-field" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
      <div className="field-gap" /><Label>Phone</Label><input className="app-field" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
      <div className="field-gap" /><Label>Ward</Label>
      <select className="app-field" value={ward} onChange={(e) => { setForm({ ...form, ward: e.target.value }); setPicked(null); }}>{wardOptions.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select>
      {byCentre && centres.length > 0 && (
        <>
          <div className="field-gap" /><Label>Registration centre</Label>
          <select aria-label="Registration centre" className="app-field" value={centre} onChange={(e) => setPicked(e.target.value)}>
            <option value="">Pick a centre</option>
            {centres.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </>
      )}
      <div className="field-gap" /><Label>Support</Label>
      <select aria-label="Support" className="app-field" value={form.support_level} onChange={(e) => setForm({ ...form, support_level: e.target.value })}>
        <option value="supporter">Supporter</option>
        <option value="undecided">Undecided</option>
        <option value="opposed">Opposed</option>
      </select>
      <label className="flex items-start gap-2 checkbox-row"><input type="checkbox" checked={form.consent_given} onChange={(e) => setForm({ ...form, consent_given: e.target.checked })} className="checkbox" />Consent to hold these details under the Data Protection Act, 2019.</label>
      {reg.isError && <div className="form-error">{reg.error.message}</div>}
      <div className="form-actions"><PrimaryBtn disabled={!ok || reg.isPending} onClick={() => reg.mutate({ campaign: campaignId, ...form, ward, registration_centre: centre || null })}>{reg.isPending ? "Saving…" : "Register supporter"}</PrimaryBtn></div>
    </Card>
  );
}

// ---- payments ---------------------------------------------------------------
const PAY_STATUS = { scheduled: "warn", sending: "warn", paid: "good", failed: "bad", cancelled: "neutral" };
const OPEN = ["scheduled", "failed"];  // still to go out: never sent, or a send that failed
const kes = (n) => `KES ${fmt(n)}`;

// The payments register: the manager schedules, pays and cancels; everyone else reads.
function PaymentsView({ campaignId, canPay, mine }) {
  const { data, isLoading, error } = usePayments(campaignId);
  const [modal, setModal] = useState(null);
  if (isLoading) return <Loading />; if (error) return <ErrorMsg error={error} />;
  const rows = data || [];
  const total = (status) => rows.filter((p) => p.status === status).reduce((s, p) => s + p.amount_kes, 0);
  const scheduled = rows.filter((p) => p.status === "scheduled");
  const actions = canPay ? (
    <div className="flex gap-2">
      {scheduled.length > 0 && <Btn onClick={() => setModal({ type: "release", payments: scheduled })}>Release all scheduled</Btn>}
      <Btn primary onClick={() => setModal({ type: "schedule" })}>Schedule payment</Btn>
    </div>
  ) : null;
  return (
    <>
      <PageTitle title={mine ? "My payments" : "Payments"} sub={`${kes(total("paid"))} paid · ${kes(total("scheduled"))} scheduled${total("failed") ? ` · ${kes(total("failed"))} failed` : ""}`} action={actions} />
      <Card pad={0}><div className="table-scroll">
        <table className="table">
          <thead><tr>
            <th>Date</th>
            {!mine && <th>Mobilizer</th>}
            <th>Event</th>
            <th className="num">Amount</th>
            <th>Status</th>
            <th>Reference</th>
            {canPay && <th/>}
          </tr></thead>
          <tbody>{rows.map((p) => (
            <tr key={p.id}>
              <td className="muted">{new Date(p.paid_at || p.created_at).toLocaleDateString()}</td>
              {!mine && <td><div className="strong">{p.recipient_name}</div><div className="meta">{p.recipient_phone || "—"}</div></td>}
              <td>{p.event_title || "—"}</td>
              <td className="num figure">{kes(p.amount_kes)}</td>
              <td><Badge text={p.status} tone={PAY_STATUS[p.status]} />{p.failure_reason && (canPay || p.status === "failed") && <div className={`failure-reason ${p.status === "failed" ? "text-bad" : "text-warn"}`}>{p.failure_reason}</div>}</td>
              <td className="muted">{p.reference || "—"}</td>
              {canPay && <td className="actions-cell">{OPEN.includes(p.status) && <div className="flex justify-end gap-2"><Btn primary onClick={() => setModal({ type: "release", payments: [p] })}>Release</Btn><Btn onClick={() => setModal({ type: "paid", payment: p })}>Mark paid</Btn><Btn onClick={() => setModal({ type: "cancel", payment: p })}>Cancel</Btn></div>}{p.status === "sending" && (p.stuck
                ? <div className="flex justify-end gap-2"><Btn onClick={() => setModal({ type: "paid", payment: p })}>Mark paid</Btn><Btn onClick={() => setModal({ type: "notsent", payment: p })}>Didn't go out</Btn></div>
                : <span className="meta">Waiting for the provider…</span>)}</td>}
            </tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={7} className="empty-row">No payments yet.</td></tr>}</tbody>
        </table>
      </div></Card>
      {modal?.type === "schedule" && <SchedulePaymentForm campaignId={campaignId} onClose={() => setModal(null)} />}
      {modal?.type === "paid" && <MarkPaidForm payment={modal.payment} onClose={() => setModal(null)} />}
      {modal?.type === "cancel" && <CancelPaymentForm payment={modal.payment} onClose={() => setModal(null)} />}
      {modal?.type === "release" && <ReleaseForm payments={modal.payments} onClose={() => setModal(null)} />}
      {modal?.type === "notsent" && <NotSentForm payment={modal.payment} onClose={() => setModal(null)} />}
    </>
  );
}

// A payment for one event; the mobilizer starts as the one the event is credited to.
function SchedulePaymentForm({ campaignId, onClose }) {
  const schedule = useSchedulePayment();
  const events = (useEvents(campaignId).data || []).filter((e) => e.status !== "cancelled");
  const mobilizers = useMobilizers(campaignId).data || [];
  const [eventId, setEventId] = useState("");
  const [picked, setPicked] = useState(null);  // null until the mobilizer box is changed
  const [amount, setAmount] = useState("");
  const event = events.find((e) => e.id === eventId);
  const mobilizer = picked ?? event?.mobilizer ?? "";
  const ok = event && mobilizer && Number.isInteger(Number(amount)) && Number(amount) > 0;
  const save = () => schedule.mutate({ campaign: campaignId, event: eventId, mobilizer, amount_kes: Number(amount) }, { onSuccess: onClose });
  return (
    <Modal title="Schedule payment" sub="Paid per event, to the mobilizer who ran it." onClose={onClose}>
      <Label>Event</Label>
      <select aria-label="Event" className="app-field" value={eventId} onChange={(e) => { setEventId(e.target.value); setPicked(null); }}>
        <option value="">Pick an event</option>
        {events.map((e) => <option key={e.id} value={e.id}>{e.title || e.ward_name}</option>)}
      </select>
      <div className="field-gap" /><Label>Mobilizer</Label>
      <select aria-label="Mobilizer" className="app-field" value={mobilizer} onChange={(e) => setPicked(e.target.value)}>
        <option value="">Pick a mobilizer</option>
        {mobilizers.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}
      </select>
      <div className="field-gap" /><Label>Amount (KES)</Label>
      <input aria-label="Amount" type="number" min={1} step={1} className="app-field" value={amount} onChange={(e) => setAmount(e.target.value)} />
      {schedule.error && <div className="form-error">{schedule.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Btn onClick={onClose}>Cancel</Btn>
        <PrimaryBtn disabled={!ok || schedule.isPending} onClick={save}>{schedule.isPending ? "Saving…" : "Schedule"}</PrimaryBtn>
      </div>
    </Modal>
  );
}

// Sends payments one after another and reports how each went.
function ReleaseForm({ payments, onClose }) {
  const payout = usePayoutMode();
  const mode = payout.data;
  const release = useReleasePayment();
  const [results, setResults] = useState(null);
  const [running, setRunning] = useState(false);
  const sum = payments.reduce((s, p) => s + p.amount_kes, 0);
  const send = async () => {
    setRunning(true);
    const out = [];
    for (const p of payments) {
      try {
        const done = await release.mutateAsync({ id: p.id });
        out.push({ p, ok: done.status === "paid", pending: done.status === "sending", text: done.status === "paid" ? done.reference : done.failure_reason || done.status });
      } catch (e) {
        out.push({ p, ok: false, text: e.message });
      }
    }
    setResults(out);
    setRunning(false);
  };
  return (
    <Modal title={payments.length === 1 ? "Release payment" : `Release ${payments.length} payments`} sub={`${kes(sum)} in total.`} onClose={running ? () => {} : onClose}>
      {payout.error && <div className="form-error">Could not tell whether releases move money: {payout.error.message}</div>}
      {mode && !mode.moves_money && <div className="notice-warn">Practice mode: no money moves. Each payment is marked paid under a PRACTICE reference.</div>}
      <div className="release-list">
        {payments.map((p) => {
          const r = results?.find((x) => x.p.id === p.id);
          return <div key={p.id} className="flex justify-between gap-3"><span><b>{p.recipient_name}</b> <span className="muted">{p.recipient_phone || "no phone"}</span></span><span>{kes(p.amount_kes)}{r && <span className={`inline-badge ${r.ok ? "text-good" : r.pending ? "text-warn" : "text-bad"}`}>{r.ok ? `Paid · ${r.text}` : r.pending ? "Sending" : r.text}</span>}</span></div>;
        })}
      </div>
      <div className="flex justify-end gap-2 form-actions">
        {results ? <PrimaryBtn onClick={onClose}>Done</PrimaryBtn> : (
          <>
            <Btn onClick={onClose} disabled={running}>Back</Btn>
            <PrimaryBtn disabled={!mode || running} onClick={send}>{running ? "Sending…" : payments.length === 1 ? "Release" : `Release ${payments.length}`}</PrimaryBtn>
          </>
        )}
      </div>
    </Modal>
  );
}

// After checking the provider: the money did not go, so the payment can be released again.
function NotSentForm({ payment, onClose }) {
  const notSent = useMarkNotSent();
  return (
    <Modal title="Didn't go out" sub={`Only if the payout provider shows that ${kes(payment.amount_kes)} to ${payment.recipient_name} was not sent. The payment can then be released again.`} onClose={onClose}>
      {notSent.error && <div className="form-error">{notSent.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Btn onClick={onClose}>Back</Btn>
        <PrimaryBtn disabled={notSent.isPending} onClick={() => notSent.mutate({ id: payment.id }, { onSuccess: onClose })}>It was not sent</PrimaryBtn>
      </div>
    </Modal>
  );
}

function MarkPaidForm({ payment, onClose }) {
  const markPaid = useMarkPaid();
  const [reference, setReference] = useState("");
  const save = () => markPaid.mutate({ id: payment.id, reference: reference.trim() }, { onSuccess: onClose });
  return (
    <Modal title="Mark paid" sub={`${kes(payment.amount_kes)} to ${payment.recipient_name}. A paid payment cannot be changed.`} onClose={onClose}>
      <Label>M-Pesa or bank reference</Label>
      <input aria-label="Reference" className="app-field" value={reference} onChange={(e) => setReference(e.target.value)} placeholder="QX12AB34" />
      {markPaid.error && <div className="form-error">{markPaid.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Btn onClick={onClose}>Back</Btn>
        <PrimaryBtn disabled={!reference.trim() || markPaid.isPending} onClick={save}>{markPaid.isPending ? "Saving…" : "Mark paid"}</PrimaryBtn>
      </div>
    </Modal>
  );
}

function CancelPaymentForm({ payment, onClose }) {
  const cancel = useCancelPayment();
  return (
    <Modal title="Cancel payment" sub={`${kes(payment.amount_kes)} to ${payment.recipient_name}. It stays on the register as cancelled.`} onClose={onClose}>
      {cancel.error && <div className="form-error">{cancel.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Btn onClick={onClose}>Back</Btn>
        <PrimaryBtn disabled={cancel.isPending} onClick={() => cancel.mutate({ id: payment.id }, { onSuccess: onClose })}>Cancel payment</PrimaryBtn>
      </div>
    </Modal>
  );
}

// ---- team -------------------------------------------------------------------
// As the API allows: the aspirant resets the manager and mobilizers, the manager resets mobilizers.
const canReset = (role, person) => person.is_active && (person.role === "mobilizer" || (person.role === "manager" && role === "candidate"));

function TeamView({ campaignId, role, onManager, onReset }) {
  const { data, isLoading, error } = useTeam(campaignId);
  if (isLoading) return <Loading />; if (error) return <ErrorMsg error={error} />;
  const people = data || [];
  const manager = people.find((p) => p.role === "manager");
  const action = role === "candidate" ? <Btn primary onClick={() => onManager(manager)}>{manager ? "Replace manager" : "Add manager"}</Btn> : null;
  return (
    <>
      <PageTitle title="Team" sub="Everyone with a login on this campaign." action={action} />
      <Card pad={0}><div className="table-scroll">
        <table className="table">
          <thead><tr><th>Name</th><th>Username</th><th>Role</th><th/></tr></thead>
          <tbody>{people.map((p) => (<tr key={p.id}><td className="strong">{p.full_name || p.username}</td><td className="muted">{p.username}</td><td>{ROLE_LABEL[p.role]}{!p.is_active && <span className="muted"> · turned off</span>}</td><td className="actions-cell">{canReset(role, p) && <Btn onClick={() => onReset(p)}>Reset password</Btn>}</td></tr>))}</tbody>
        </table>
      </div></Card>
      {!manager && role === "candidate" && <div className="page-note">This campaign has no manager yet. Add one to run the day-to-day.</div>}
    </>
  );
}

// The aspirant adds the manager, or replaces `sitting`, whose login is then turned off.
function ManagerForm({ campaignId, sitting, onClose }) {
  const set = useSetManager();
  const [name, setName] = useState(""); const [username, setUsername] = useState(""); const [phone, setPhone] = useState("");
  const ok = name.trim() && username.trim().length >= 3;
  const made = set.data;

  if (made) {
    return (
      <PasswordModal title="Manager added" password={made.password} onClose={onClose}>
        <b>{made.username}</b> can now sign in and run this campaign.{made.replaced && <> {made.replaced} is off the campaign and can no longer sign in.</>}
      </PasswordModal>
    );
  }

  const save = () => {
    const [first, ...rest] = name.trim().split(/\s+/);
    set.mutate({ campaign: campaignId, username: username.trim().toLowerCase(), first_name: first, last_name: rest.join(" "), phone: phone.trim(), replace: !!sitting });
  };
  return (
    <Modal title={sitting ? "Replace manager" : "Add manager"} sub={sitting ? `${sitting.full_name || sitting.username} comes off the campaign and their login is turned off.` : "One manager per campaign. They add mobilizers and run the day-to-day."} onClose={onClose}>
      <Label>Full name</Label><input aria-label="Full name" className="app-field" value={name} onChange={(e) => setName(e.target.value)} />
      <div className="field-gap" /><Label>Username</Label><input aria-label="Username" className="app-field" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="amina" />
      <div className="field-gap" /><Label>Phone</Label><input aria-label="Phone" className="app-field" value={phone} onChange={(e) => setPhone(e.target.value)} />
      {set.error && <div className="form-error">{set.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Btn onClick={onClose}>Cancel</Btn>
        <PrimaryBtn disabled={!ok || set.isPending} onClick={save}>{set.isPending ? "Saving…" : sitting ? "Replace manager" : "Add manager"}</PrimaryBtn>
      </div>
    </Modal>
  );
}

function ResetPasswordForm({ campaignId, person, onClose }) {
  const reset = useResetTeamPassword();
  const name = person.full_name || person.username;
  if (reset.data) {
    return (
      <PasswordModal title="New password" password={reset.data.password} onClose={onClose}>
        <b>{reset.data.username}</b> signs in with this from now on. Their old password no longer works.
      </PasswordModal>
    );
  }
  return (
    <Modal title={`Reset ${name}'s password`} sub="Their old password stops working and they are signed out." onClose={onClose}>
      {reset.error && <div className="form-error">{reset.error.message}</div>}
      <div className={`flex justify-end gap-2 ${reset.error ? "form-actions" : ""}`.trim()}>
        <Btn onClick={onClose}>Cancel</Btn>
        <PrimaryBtn disabled={reset.isPending} onClick={() => reset.mutate({ campaign: campaignId, user: person.id })}>{reset.isPending ? "Resetting…" : "Reset password"}</PrimaryBtn>
      </div>
    </Modal>
  );
}

// ---- nav ------------------------------------------------------------------
const NAV = {
  candidate: [["overview", "Overview"], ["units", "Ward performance"], ["events", "Events"], ["mobilizers", "Mobilizers"], ["team", "Team"], ["payments", "Payments"], ["strategy", "Strategy"]],
  manager: [["overview", "Overview"], ["targets", "Targets"], ["units", "Wards"], ["events", "Events"], ["mobilizers", "Mobilizers"], ["team", "Team"], ["supporters", "Supporters"], ["payments", "Payments"], ["strategy", "Strategy"]],
  mobilizer: [["myevents", "My events"], ["register", "Register supporter"], ["mysupporters", "My supporters"], ["mypayments", "My payments"]],
};
const ROLE_LABEL = { candidate: "Candidate", manager: "Campaign Manager", mobilizer: "Mobilizer" };

// ---- root -----------------------------------------------------------------
export default function App() {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  const role = user?.role || "candidate";
  const nav = NAV[role] || NAV.candidate;

  const [page, setPage] = useState(nav[0][0]);
  const [modal, setModal] = useState(null);

  const campaigns = useCampaigns();
  const campaign = (campaigns.data || [])[0];
  const campaignId = campaign?.id;

  const strategy = useStrategy(campaignId);
  const events = useEvents(campaignId);
  const targets = useTargets(campaignId); // used for ward options in forms
  const mobilizers = useMobilizers(campaignId);
  const units = useMemo(() => (targets.data || []).map((t) => ({
    key: t.id, ward: t.ward, registration_centre: t.registration_centre ?? null, name: t.centre_name || t.ward_name,
  })), [targets.data]);
  const canAssign = role === "manager" || role === "candidate";
  const assign = canAssign ? (unit, holder) => setModal({ type: "assign", unit, holder }) : undefined;

  // ward options for forms: distinct wards from targets
  const wardOptions = useMemo(() => {
    const seen = {}; const out = [];
    (targets.data || []).forEach((t) => { if (t.ward && !seen[t.ward]) { seen[t.ward] = 1; out.push({ id: t.ward, name: t.ward_name }); } });
    return out;
  }, [targets.data]);

  if (campaigns.isLoading) return <Loading />;
  if (campaigns.error) return <ErrorMsg error={campaigns.error} />;
  if (!campaign) return <div className="not-on-campaign">You are not on a campaign yet.</div>;

  function renderPage() {
    switch (page) {
      case "overview":
        if (strategy.isLoading) return <Loading />; if (strategy.error) return <ErrorMsg error={strategy.error} />;
        return (<><PageTitle title="Overview" sub={role === "candidate" ? "Where the campaign stands today." : "Your command view of the seat."} />
          <div className="overview-stack">
            <TallyHero s={strategy.data} />
            <div className="grid gap-5 overview-grid">
              <UnitRegister units={strategy.data.units} mobilizers={mobilizers.data || []} onAssign={assign} />
              <StrategyPanel notes={strategy.data.notes} />
            </div>
          </div></>);
      case "units":
        if (strategy.isLoading) return <Loading />; if (strategy.error) return <ErrorMsg error={strategy.error} />;
        return (<><PageTitle title={role === "candidate" ? "Ward performance" : "Wards"} sub="Win number, progress and coverage per unit." /><UnitRegister units={strategy.data.units} mobilizers={mobilizers.data || []} onAssign={assign} /></>);
      case "strategy":
        if (strategy.isLoading) return <Loading />; if (strategy.error) return <ErrorMsg error={strategy.error} />;
        return (<><PageTitle title="Strategy read" sub="Your next moves, computed from your own data." /><StrategyPanel notes={strategy.data.notes} /></>);
      case "targets": return <TargetsView campaignId={campaignId} />;
      case "team": return <TeamView campaignId={campaignId} role={role} onManager={(sitting) => setModal({ type: "manager", sitting })} onReset={(person) => setModal({ type: "reset", person })} />;
      case "mobilizers": return <MobilizersView campaignId={campaignId} units={units} byCentre={campaign.operational_grain === "centre"} onAdd={() => setModal({ type: "mobilizer" })} onEdit={(m) => setModal({ type: "mobilizer", mobilizer: m })} />;
      case "supporters": return <SupportersView campaignId={campaignId} share={campaign} centreWard={campaign.operational_grain === "centre" ? campaign.ward : null} />;
      case "events":
      case "myevents":
        if (events.isLoading) return <Loading />; if (events.error) return <ErrorMsg error={events.error} />;
        return (<><PageTitle title={page === "myevents" ? "My events" : "Events"} sub="Rallies and meetings, with mobilization counts." action={role !== "candidate" ? <Btn primary onClick={() => setModal({ type: "event" })}>Schedule event</Btn> : null} /><EventList events={events.data || []} showActions={role !== "candidate"} onRecord={(e) => setModal({ type: "record", event: e })} onInvite={(e) => setModal({ type: "invite", event: e })} onQr={role !== "candidate" ? (e) => setModal({ type: "qr", event: e }) : undefined} /></>);
      case "register": return (<><PageTitle title="Register a supporter" sub="Quick capture in the field." /><RegisterSupporterForm campaignId={campaignId} wardOptions={wardOptions} byCentre={campaign.operational_grain === "centre"} /></>);
      case "mysupporters": return <SupportersView campaignId={campaignId} centreWard={campaign.operational_grain === "centre" ? campaign.ward : null} />;
      case "payments": return <PaymentsView campaignId={campaignId} canPay={role === "manager"} />;
      case "mypayments": return <PaymentsView campaignId={campaignId} mine />;
      default: return null;
    }
  }

  return (
    <div className="app-shell">
      <div className="topbar">
        <div className="mx-auto flex flex-wrap items-center justify-between gap-3 topbar-inner">
          <div className="flex items-center gap-3 topbar-identity"><div className="brand">MZIGO<span className="brand-mark">·</span>CRM</div><div className="topbar-divider" /><div><div className="topbar-campaign">{campaign.title}</div><div className="topbar-meta">{[campaign.candidate_name && `for ${campaign.candidate_name}`, campaign.seat, campaign.area_name].filter(Boolean).join(" · ")}</div></div></div>
          <div className="flex items-center gap-3"><span className="topbar-user">{user?.full_name || user?.username} · {ROLE_LABEL[role]}</span><Btn onClick={logout}>Sign out</Btn></div>
        </div>
      </div>

      <div className="mx-auto layout">
        <nav className="sidebar">
          <div className="sidebar-label">{ROLE_LABEL[role].toUpperCase()}</div>
          <div className="nav">
            {nav.map(([key, label]) => <button key={key} type="button" aria-current={page === key ? "page" : undefined} onClick={() => setPage(key)} className={`nav-item ${page === key ? "nav-item-active" : ""}`.trim()}>{label}</button>)}
          </div>
        </nav>

        <main className="main">
          {renderPage()}
        </main>
      </div>

      {modal?.type === "mobilizer" && <MobilizerForm campaignId={campaignId} units={units} byCentre={campaign.operational_grain === "centre"} mobilizers={mobilizers.data || []} mobilizer={modal.mobilizer} onClose={() => setModal(null)} />}
      {modal?.type === "manager" && <ManagerForm campaignId={campaignId} sitting={modal.sitting} onClose={() => setModal(null)} />}
      {modal?.type === "reset" && <ResetPasswordForm campaignId={campaignId} person={modal.person} onClose={() => setModal(null)} />}
      {modal?.type === "assign" && <AssignMobilizerForm unit={modal.unit} holder={modal.holder} mobilizers={mobilizers.data || []} onClose={() => setModal(null)} />}
      {modal?.type === "event" && <ScheduleEventForm campaignId={campaignId} wardOptions={wardOptions} byCentre={campaign.operational_grain === "centre"} onClose={() => setModal(null)} />}
      {modal?.type === "record" && <RecordForm event={modal.event} onClose={() => setModal(null)} />}
      {modal?.type === "invite" && <InviteForm event={modal.event} onClose={() => setModal(null)} />}
      {modal?.type === "qr" && <QrModal event={modal.event} canClose={role === "manager"} onClose={() => setModal(null)} />}
    </div>
  );
}
