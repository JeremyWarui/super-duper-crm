// src/App.jsx  — the live-wired campaign dashboard.
// Role comes from the logged-in user; every page reads React Query hooks; the
// three forms fire real mutations. Same war-room UI as the prototype.
import React, { useState, useMemo } from "react";
import { useAuth } from "./store/auth";
import {
  useCampaigns, useStrategy, useTargets, useEvents, useMobilizers, useSupporters,
  useScheduleEvent, useRecordEvent, useAddMobilizer, useRegisterSupporter, useUpdateTarget,
} from "./api/hooks";

const C = {
  ink: "#171C1F", paper: "#E9EBE6", panel: "#FFFFFF",
  green: "#0B6B3A", greenSoft: "#E1EEE7", red: "#B4231F", redSoft: "#F6E3E1",
  amber: "#B9791A", amberSoft: "#F4EAD6", line: "#D7DBD4", sub: "#5C655F", railBg: "#141A16",
};
const DISPLAY = { fontFamily: "Oswald, Impact, sans-serif" };
const FIELD = { width: "100%", padding: "10px 12px", borderRadius: 8, border: `1px solid ${C.line}`, fontSize: 14, marginTop: 6, background: C.panel, fontFamily: "inherit" };
const fmt = (n) => Number(n || 0).toLocaleString();

// ---- status helper (server gives progress; we colour it) ------------------
function statusOf(progress) {
  if (progress >= 1) return { label: "Target met", color: C.green, soft: C.greenSoft };
  if (progress >= 0.6) return { label: "Building", color: C.amber, soft: C.amberSoft };
  return { label: "Behind", color: C.red, soft: C.redSoft };
}

// ---- shared UI ------------------------------------------------------------
const Badge = ({ text, color, soft }) => <span style={{ padding: "1px 8px", borderRadius: 999, fontSize: 11, fontWeight: 600, color, background: soft }}>{text}</span>;
const Bar = ({ pct, color }) => <div style={{ height: 8, background: C.paper, borderRadius: 999, overflow: "hidden", border: `1px solid ${C.line}` }}><div style={{ width: `${Math.min(pct, 100)}%`, height: "100%", background: color }} /></div>;
const Card = ({ children, pad = 18, style }) => <div style={{ background: C.panel, border: `1px solid ${C.line}`, borderRadius: 14, padding: pad, ...style }}>{children}</div>;
const Label = ({ children }) => <div style={{ fontSize: 13, fontWeight: 600 }}>{children}</div>;
const Btn = ({ children, onClick, primary, disabled }) => <button onClick={onClick} disabled={disabled} style={{ padding: "8px 14px", borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: disabled ? "default" : "pointer", border: `1px solid ${primary ? C.green : C.line}`, background: disabled ? C.line : primary ? C.green : C.panel, color: primary ? "#fff" : C.ink }}>{children}</button>;
const PrimaryBtn = ({ children, onClick, disabled }) => <button onClick={onClick} disabled={disabled} style={{ padding: "9px 18px", borderRadius: 8, border: "none", background: disabled ? C.line : C.green, color: "#fff", ...DISPLAY, fontWeight: 600, fontSize: 14, cursor: disabled ? "default" : "pointer" }}>{children}</button>;
const PageTitle = ({ title, sub, action }) => <div className="flex flex-wrap items-end justify-between gap-3" style={{ marginBottom: 16 }}><div><div style={{ ...DISPLAY, fontSize: 24, fontWeight: 700, lineHeight: 1.05 }}>{title}</div>{sub && <div style={{ color: C.sub, fontSize: 13, marginTop: 3 }}>{sub}</div>}</div>{action}</div>;
const Loading = () => <div style={{ color: C.sub, fontSize: 14, padding: 20 }}>Loading…</div>;
const ErrorMsg = ({ error }) => <div style={{ color: C.red, fontSize: 14, padding: 20 }}>{error?.message || "Something went wrong."}</div>;

const Modal = ({ title, sub, onClose, children }) => (
  <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(20,26,22,.45)", display: "flex", alignItems: "flex-start", justifyContent: "center", padding: "6vh 16px", zIndex: 50 }}>
    <div onClick={(e) => e.stopPropagation()} style={{ background: C.panel, borderRadius: 14, width: "100%", maxWidth: 440 }}>
      <div className="flex items-start justify-between" style={{ padding: "18px 20px", borderBottom: `1px solid ${C.line}` }}>
        <div><div style={{ ...DISPLAY, fontSize: 20, fontWeight: 700 }}>{title}</div>{sub && <div style={{ fontSize: 12.5, color: C.sub, marginTop: 2 }}>{sub}</div>}</div>
        <button onClick={onClose} style={{ border: "none", background: "transparent", fontSize: 22, cursor: "pointer", color: C.sub }}>×</button>
      </div>
      <div style={{ padding: 20 }}>{children}</div>
    </div>
  </div>
);

// ---- dashboard blocks (fed by the /strategy/ endpoint) --------------------
function TallyHero({ s }) {
  const crossed = s.committed >= s.win_number;
  const cast = s.total_cast || s.win_number * 2;
  return (
    <Card pad={22}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div style={{ ...DISPLAY, fontSize: 15, fontWeight: 600 }}>VOTES TO WIN THE SEAT</div>
        <div style={{ fontSize: 13, color: C.sub }}>{s.units.length} units · {fmt(cast)} projected votes cast</div>
      </div>
      <div className="flex flex-wrap items-end gap-6" style={{ marginTop: 6 }}>
        <span style={{ ...DISPLAY, fontSize: 58, fontWeight: 700, lineHeight: 0.9, color: crossed ? C.green : C.ink }}>{fmt(s.win_number)}</span>
        <div style={{ paddingBottom: 8 }}>
          <div style={{ ...DISPLAY, fontSize: 24, fontWeight: 600, color: crossed ? C.green : C.amber }}>{fmt(s.committed)} committed</div>
          <div style={{ fontSize: 13, color: C.sub }}>{s.progress_pct}% there · {fmt(Math.max(s.win_number - s.committed, 0))} to go</div>
        </div>
      </div>
      <div style={{ position: "relative", marginTop: 20, height: 40 }}>
        <div style={{ position: "absolute", inset: 0, background: C.paper, borderRadius: 8, border: `1px solid ${C.line}` }} />
        <div style={{ position: "absolute", top: 0, bottom: 0, left: 0, width: `${(s.committed / cast) * 100}%`, background: crossed ? C.green : C.amber, borderRadius: "8px 0 0 8px" }} />
        <div style={{ position: "absolute", top: -6, bottom: -6, left: `${(s.win_number / cast) * 100}%`, width: 2, background: C.ink }} />
        <div style={{ position: "absolute", top: -20, left: `${(s.win_number / cast) * 100}%`, transform: "translateX(-50%)", ...DISPLAY, fontSize: 11, fontWeight: 600, letterSpacing: 1 }}>WIN LINE</div>
      </div>
      <div className="flex flex-wrap gap-x-8 gap-y-2" style={{ marginTop: 22 }}>
        {[["Registered voters", fmt(s.total_registered)], ["Units covered", `${s.units.filter((u) => u.events > 0).length} / ${s.units.length}`],
          ["Mobilizers", `${s.units.filter((u) => u.has_mobilizer).length} / ${s.units.length}`], ["Units behind", String(s.units.filter((u) => u.progress < 0.6).length)]].map(([k, v]) => (
          <div key={k}><div style={{ ...DISPLAY, fontSize: 22, fontWeight: 600 }}>{v}</div><div style={{ fontSize: 12, color: C.sub }}>{k}</div></div>
        ))}
      </div>
    </Card>
  );
}

function UnitRegister({ units, readOnly, onAssign }) {
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
      <div className="flex flex-wrap items-center justify-between gap-2" style={{ padding: "14px 18px", borderBottom: `1px solid ${C.line}` }}>
        <div style={{ ...DISPLAY, fontSize: 16, fontWeight: 600 }}>Targeting</div>
        <div className="flex gap-1" style={{ fontSize: 12 }}>
          {[["opportunity", "Biggest gap"], ["needed", "Win number"], ["progress", "Least progress"]].map(([k, l]) => (
            <button key={k} onClick={() => setSortKey(k)} style={{ padding: "5px 10px", borderRadius: 999, cursor: "pointer", border: `1px solid ${sortKey === k ? C.ink : C.line}`, background: sortKey === k ? C.ink : "transparent", color: sortKey === k ? "#fff" : C.sub }}>{l}</button>
          ))}
        </div>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
          <thead><tr style={{ color: C.sub, textAlign: "left" }}>
            <th style={{ padding: "10px 18px", fontWeight: 500 }}>Unit</th>
            <th style={{ padding: "10px 8px", fontWeight: 500, textAlign: "right" }}>Need</th>
            <th style={{ padding: "10px 8px", fontWeight: 500 }}>Progress</th>
            <th style={{ padding: "10px 8px", fontWeight: 500, textAlign: "center" }}>Events</th>
            <th style={{ padding: "10px 18px", fontWeight: 500 }}>Mobilizer</th>
          </tr></thead>
          <tbody>
            {sorted.map((u) => {
              const st = statusOf(u.progress);
              return (
                <tr key={u.unit} style={{ borderTop: `1px solid ${C.line}` }}>
                  <td style={{ padding: "12px 18px" }}><div style={{ fontWeight: 600 }}>{u.unit}</div><div style={{ marginTop: 3 }}><Badge text={st.label} color={st.color} soft={st.soft} /></div></td>
                  <td style={{ padding: "12px 8px", textAlign: "right", ...DISPLAY, fontWeight: 600, fontSize: 15 }}>{fmt(u.needed)}</td>
                  <td style={{ padding: "12px 8px", minWidth: 140 }}><Bar pct={u.progress * 100} color={st.color} /><div style={{ fontSize: 11, color: C.sub, marginTop: 3 }}>{fmt(u.committed)} · {Math.round(u.progress * 100)}%</div></td>
                  <td style={{ padding: "12px 8px", textAlign: "center", ...DISPLAY, fontWeight: 600, color: u.events === 0 ? C.red : C.ink }}>{u.events}</td>
                  <td style={{ padding: "12px 18px", color: u.has_mobilizer ? C.green : C.red }}>{u.has_mobilizer ? "Assigned" : (readOnly ? "Unassigned" : <Btn onClick={onAssign}>Assign</Btn>)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

const StrategyPanel = ({ notes, dark }) => (
  <div style={{ background: dark ? C.ink : C.panel, color: dark ? "#fff" : C.ink, border: dark ? "none" : `1px solid ${C.line}`, borderRadius: 14, padding: "18px 20px" }}>
    <div style={{ ...DISPLAY, fontSize: 16, fontWeight: 600, color: dark ? "#fff" : C.ink }}>Strategy read</div>
    <div style={{ fontSize: 12.5, color: dark ? "#AEB6B0" : C.sub, marginTop: 2 }}>Computed from your targets, events and mobilizers.</div>
    <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      {(notes || []).map((n, i) => (
        <div key={i} style={{ borderLeft: `3px solid ${n.tone === "go" ? C.green : C.amber}`, paddingLeft: 12 }}>
          <div style={{ ...DISPLAY, fontSize: 14.5, fontWeight: 600, color: dark ? "#fff" : C.ink }}>{n.title}</div>
          <div style={{ fontSize: 13, color: dark ? "#C7CDC8" : C.sub, marginTop: 2, lineHeight: 1.45 }}>{n.text}</div>
        </div>
      ))}
      {(!notes || notes.length === 0) && <div style={{ fontSize: 13, color: dark ? "#AEB6B0" : C.sub }}>No flags right now — coverage looks balanced.</div>}
    </div>
  </div>
);

// ---- forms (fire mutations) ----------------------------------------------
function AddMobilizerForm({ campaignId, wardOptions, onClose }) {
  const add = useAddMobilizer();
  const [name, setName] = useState(""); const [phone, setPhone] = useState("");
  const [ward, setWard] = useState(wardOptions[0]?.id || "");
  const ok = name.trim() && ward;
  return (
    <Modal title="Add mobilizer" sub="One ground organiser per ward." onClose={onClose}>
      <Label>Full name</Label><input style={FIELD} value={name} onChange={(e) => setName(e.target.value)} />
      <div style={{ height: 14 }} /><Label>Phone</Label><input style={FIELD} value={phone} onChange={(e) => setPhone(e.target.value)} />
      <div style={{ height: 14 }} /><Label>Ward</Label>
      <select style={FIELD} value={ward} onChange={(e) => setWard(e.target.value)}>{wardOptions.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select>
      {add.isError && <div style={{ color: C.red, fontSize: 12.5, marginTop: 8 }}>{add.error.message}</div>}
      <div className="flex justify-end gap-2" style={{ marginTop: 22 }}>
        <Btn onClick={onClose}>Cancel</Btn>
        <PrimaryBtn disabled={!ok || add.isPending} onClick={() => add.mutate({ campaign: campaignId, ward, full_name: name.trim(), phone: phone.trim() }, { onSuccess: onClose })}>{add.isPending ? "Saving…" : "Save mobilizer"}</PrimaryBtn>
      </div>
    </Modal>
  );
}

function ScheduleEventForm({ campaignId, wardOptions, onClose }) {
  const schedule = useScheduleEvent();
  const [title, setTitle] = useState(""); const [venue, setVenue] = useState(""); const [date, setDate] = useState("");
  const [ward, setWard] = useState(wardOptions[0]?.id || "");
  const ok = title.trim() && ward && date;
  return (
    <Modal title="Schedule event" sub="Attendance is recorded after it happens." onClose={onClose}>
      <Label>Event title</Label><input style={FIELD} value={title} onChange={(e) => setTitle(e.target.value)} />
      <div style={{ height: 14 }} /><Label>Ward</Label>
      <select style={FIELD} value={ward} onChange={(e) => setWard(e.target.value)}>{wardOptions.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select>
      <div style={{ height: 14 }} /><Label>Venue</Label><input style={FIELD} value={venue} onChange={(e) => setVenue(e.target.value)} />
      <div style={{ height: 14 }} /><Label>Date</Label><input type="date" style={FIELD} value={date} onChange={(e) => setDate(e.target.value)} />
      {schedule.isError && <div style={{ color: C.red, fontSize: 12.5, marginTop: 8 }}>{schedule.error.message}</div>}
      <div className="flex justify-end gap-2" style={{ marginTop: 22 }}>
        <Btn onClick={onClose}>Cancel</Btn>
        <PrimaryBtn disabled={!ok || schedule.isPending} onClick={() => schedule.mutate({ campaign: campaignId, ward, title: title.trim(), venue: venue.trim(), scheduled_date: date, status: "planned" }, { onSuccess: onClose })}>{schedule.isPending ? "Saving…" : "Schedule event"}</PrimaryBtn>
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
      <Label>How many were reached / invited</Label><input type="number" style={FIELD} value={reached} onChange={(e) => setReached(e.target.value)} />
      <div style={{ height: 14 }} /><Label>How many attended</Label><input type="number" style={FIELD} value={attended} onChange={(e) => setAttended(e.target.value)} />
      {reached !== "" && attended !== "" && a > r && <div style={{ color: C.red, fontSize: 12, marginTop: 8 }}>Attendance can't exceed those reached.</div>}
      {record.isError && <div style={{ color: C.red, fontSize: 12.5, marginTop: 8 }}>{record.error.message}</div>}
      <div className="flex justify-end gap-2" style={{ marginTop: 22 }}>
        <Btn onClick={onClose}>Cancel</Btn>
        <PrimaryBtn disabled={!ok || record.isPending} onClick={() => record.mutate({ id: event.id, number_reached: r, number_attended: a }, { onSuccess: onClose })}>{record.isPending ? "Saving…" : "Save & mark done"}</PrimaryBtn>
      </div>
    </Modal>
  );
}

// ---- events + supporters lists -------------------------------------------
function EventList({ events, showActions, onRecord }) {
  return (
    <Card pad={0}><div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
        <thead><tr style={{ color: C.sub, textAlign: "left" }}>
          <th style={{ padding: "10px 18px", fontWeight: 500 }}>Event</th><th style={{ padding: "10px 8px", fontWeight: 500 }}>Ward</th>
          <th style={{ padding: "10px 8px", fontWeight: 500 }}>Date</th><th style={{ padding: "10px 8px", fontWeight: 500 }}>Status</th>
          <th style={{ padding: "10px 8px", fontWeight: 500, textAlign: "right" }}>Reached</th><th style={{ padding: "10px 8px", fontWeight: 500, textAlign: "right" }}>Attended</th>
          <th style={{ padding: "10px 18px", fontWeight: 500, textAlign: "right" }}>Turnout</th>
        </tr></thead>
        <tbody>
          {events.map((e) => {
            const done = e.status === "done";
            return (
              <tr key={e.id} style={{ borderTop: `1px solid ${C.line}` }}>
                <td style={{ padding: "12px 18px", fontWeight: 600 }}>{e.title}<div style={{ fontSize: 12, color: C.sub, fontWeight: 400 }}>{e.venue || "—"}</div></td>
                <td style={{ padding: "12px 8px" }}>{e.ward_name}</td>
                <td style={{ padding: "12px 8px" }}>{e.scheduled_date ? new Date(e.scheduled_date).toLocaleDateString("en-GB", { day: "numeric", month: "short" }) : "—"}</td>
                <td style={{ padding: "12px 8px" }}><Badge text={done ? "Done" : "Planned"} color={done ? C.green : C.amber} soft={done ? C.greenSoft : C.amberSoft} /></td>
                <td style={{ padding: "12px 8px", textAlign: "right" }}>{done ? fmt(e.number_reached) : (showActions ? <Btn onClick={() => onRecord(e)}>Record</Btn> : "—")}</td>
                <td style={{ padding: "12px 8px", textAlign: "right" }}>{done ? fmt(e.number_attended) : "—"}</td>
                <td style={{ padding: "12px 18px", textAlign: "right", ...DISPLAY, fontWeight: 600 }}>{done ? `${e.turnout_pct}%` : "—"}</td>
              </tr>
            );
          })}
          {events.length === 0 && <tr><td colSpan={7} style={{ padding: 20, color: C.sub }}>No events yet.</td></tr>}
        </tbody>
      </table>
    </div></Card>
  );
}

function SupportersView({ campaignId }) {
  const { data, isLoading, error } = useSupporters(campaignId);
  const [filter, setFilter] = useState("all");
  if (isLoading) return <Loading />; if (error) return <ErrorMsg error={error} />;
  const all = data || [];
  const shown = filter === "all" ? all : all.filter((s) => s.support_level === filter);
  const col = { supporter: [C.green, C.greenSoft], undecided: [C.amber, C.amberSoft], opposed: [C.red, C.redSoft] };
  return (
    <>
      <PageTitle title="Supporters" sub={`${all.length} on the register`} />
      <div className="flex gap-1" style={{ marginBottom: 12, fontSize: 12 }}>
        {["all", "supporter", "undecided", "opposed"].map((f) => <button key={f} onClick={() => setFilter(f)} style={{ padding: "6px 12px", borderRadius: 999, cursor: "pointer", textTransform: "capitalize", border: `1px solid ${filter === f ? C.ink : C.line}`, background: filter === f ? C.ink : "transparent", color: filter === f ? "#fff" : C.sub }}>{f}</button>)}
      </div>
      <Card pad={0}><div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
          <thead><tr style={{ color: C.sub, textAlign: "left" }}><th style={{ padding: "10px 18px", fontWeight: 500 }}>Name</th><th style={{ padding: "10px 8px", fontWeight: 500 }}>Phone</th><th style={{ padding: "10px 8px", fontWeight: 500 }}>Support</th><th style={{ padding: "10px 18px", fontWeight: 500 }}>Consent</th></tr></thead>
          <tbody>{shown.map((s) => (<tr key={s.id} style={{ borderTop: `1px solid ${C.line}` }}><td style={{ padding: "12px 18px", fontWeight: 600 }}>{s.full_name}</td><td style={{ padding: "12px 8px", color: C.sub }}>{s.phone}</td><td style={{ padding: "12px 8px" }}><Badge text={s.support_level} color={col[s.support_level]?.[0] || C.sub} soft={col[s.support_level]?.[1] || C.paper} /></td><td style={{ padding: "12px 18px" }}>{s.consent_given ? <span style={{ color: C.green }}>✓</span> : <span style={{ color: C.red }}>missing</span>}</td></tr>))}
          {shown.length === 0 && <tr><td colSpan={4} style={{ padding: 20, color: C.sub }}>None yet.</td></tr>}</tbody>
        </table>
      </div></Card>
    </>
  );
}

function TargetsView({ campaignId }) {
  const { data, isLoading, error } = useTargets(campaignId);
  const update = useUpdateTarget();
  if (isLoading) return <Loading />; if (error) return <ErrorMsg error={error} />;
  const rows = data || [];
  const total = rows.reduce((s, t) => s + (t.votes_needed || 0), 0);
  return (
    <>
      <PageTitle title="Targets — the win number" sub="Set projected turnout per unit; the win number recomputes on the server." />
      <Card pad={0}><div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
          <thead><tr style={{ color: C.sub, textAlign: "left" }}><th style={{ padding: "10px 18px", fontWeight: 500 }}>Unit</th><th style={{ padding: "10px 8px", fontWeight: 500, textAlign: "right" }}>Registered</th><th style={{ padding: "10px 8px", fontWeight: 500, textAlign: "center" }}>Turnout %</th><th style={{ padding: "10px 18px", fontWeight: 500, textAlign: "right" }}>Votes needed</th></tr></thead>
          <tbody>{rows.map((t) => (
            <tr key={t.id} style={{ borderTop: `1px solid ${C.line}` }}>
              <td style={{ padding: "12px 18px", fontWeight: 600 }}>{t.centre_name || t.ward_name}</td>
              <td style={{ padding: "12px 8px", textAlign: "right" }}>{fmt(t.registered_voters)}</td>
              <td style={{ padding: "10px 8px", textAlign: "center" }}>
                <input type="range" min={40} max={85} defaultValue={Math.round(t.projected_turnout_pct || 60)} onMouseUp={(e) => update.mutate({ id: t.id, projected_turnout_pct: Number(e.target.value) })} onTouchEnd={(e) => update.mutate({ id: t.id, projected_turnout_pct: Number(e.target.value) })} style={{ width: 90, accentColor: C.green }} />
                <span style={{ ...DISPLAY, marginLeft: 8, fontWeight: 600 }}>{Math.round(t.projected_turnout_pct || 60)}%</span>
              </td>
              <td style={{ padding: "12px 18px", textAlign: "right", ...DISPLAY, fontWeight: 700, fontSize: 16, color: C.green }}>{fmt(t.votes_needed)}</td>
            </tr>
          ))}</tbody>
          <tfoot><tr style={{ borderTop: `2px solid ${C.ink}` }}><td style={{ padding: "12px 18px", ...DISPLAY, fontWeight: 700 }} colSpan={3}>TOTAL WIN NUMBER</td><td style={{ padding: "12px 18px", textAlign: "right", ...DISPLAY, fontWeight: 700, fontSize: 18 }}>{fmt(total)}</td></tr></tfoot>
        </table>
      </div></Card>
      <div style={{ fontSize: 12, color: C.sub, marginTop: 10 }}>Release a slider to save — the server recomputes the win number and the dashboard updates.</div>
    </>
  );
}

function MobilizersView({ campaignId, onAdd }) {
  const { data, isLoading, error } = useMobilizers(campaignId);
  if (isLoading) return <Loading />; if (error) return <ErrorMsg error={error} />;
  return (
    <>
      <PageTitle title="Mobilizers" sub="Ground organisers by ward." action={<Btn primary onClick={onAdd}>Add mobilizer</Btn>} />
      <Card pad={0}><div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
          <thead><tr style={{ color: C.sub, textAlign: "left" }}><th style={{ padding: "10px 18px", fontWeight: 500 }}>Name</th><th style={{ padding: "10px 8px", fontWeight: 500 }}>Ward</th><th style={{ padding: "10px 18px", fontWeight: 500 }}>Phone</th></tr></thead>
          <tbody>{(data || []).map((m) => (<tr key={m.id} style={{ borderTop: `1px solid ${C.line}` }}><td style={{ padding: "12px 18px", fontWeight: 600 }}>{m.full_name}</td><td style={{ padding: "12px 8px" }}>{m.ward_name}</td><td style={{ padding: "12px 18px", color: C.sub }}>{m.phone || "—"}</td></tr>))}
          {(!data || data.length === 0) && <tr><td colSpan={3} style={{ padding: 20, color: C.sub }}>No mobilizers yet.</td></tr>}</tbody>
        </table>
      </div></Card>
    </>
  );
}

function RegisterSupporterForm({ campaignId, wardOptions }) {
  const reg = useRegisterSupporter();
  const [form, setForm] = useState({ full_name: "", phone: "", ward: wardOptions[0]?.id || "", consent_given: false });
  const ok = form.full_name.trim() && form.consent_given;
  if (reg.isSuccess) return <Card pad={24}><div style={{ ...DISPLAY, fontSize: 22, fontWeight: 700, color: C.green }}>Registered.</div><div style={{ marginTop: 12 }}><Btn onClick={() => reg.reset()}>Register another</Btn></div></Card>;
  return (
    <Card pad={22}>
      <Label>Full name</Label><input style={FIELD} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
      <div style={{ height: 14 }} /><Label>Phone</Label><input style={FIELD} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
      <div style={{ height: 14 }} /><Label>Ward</Label>
      <select style={FIELD} value={form.ward} onChange={(e) => setForm({ ...form, ward: e.target.value })}>{wardOptions.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select>
      <label className="flex items-start gap-2" style={{ marginTop: 14, fontSize: 12.5, color: C.sub, cursor: "pointer" }}><input type="checkbox" checked={form.consent_given} onChange={(e) => setForm({ ...form, consent_given: e.target.checked })} style={{ marginTop: 2, accentColor: C.green }} />Consent to hold these details under the Data Protection Act, 2019.</label>
      {reg.isError && <div style={{ color: C.red, fontSize: 12.5, marginTop: 8 }}>{reg.error.message}</div>}
      <div style={{ marginTop: 16 }}><PrimaryBtn disabled={!ok || reg.isPending} onClick={() => reg.mutate({ campaign: campaignId, ...form })}>{reg.isPending ? "Saving…" : "Register supporter"}</PrimaryBtn></div>
    </Card>
  );
}

// ---- nav ------------------------------------------------------------------
const NAV = {
  candidate: [["overview", "Overview"], ["units", "Ward performance"], ["events", "Events"], ["strategy", "Strategy"]],
  manager: [["overview", "Overview"], ["targets", "Targets"], ["units", "Wards"], ["events", "Events"], ["mobilizers", "Mobilizers"], ["supporters", "Supporters"], ["strategy", "Strategy"]],
  mobilizer: [["myevents", "My events"], ["register", "Register supporter"], ["mysupporters", "My supporters"]],
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

  // ward options for forms: distinct wards from targets
  const wardOptions = useMemo(() => {
    const seen = {}; const out = [];
    (targets.data || []).forEach((t) => { if (t.ward && !seen[t.ward]) { seen[t.ward] = 1; out.push({ id: t.ward, name: t.ward_name }); } });
    return out;
  }, [targets.data]);

  if (campaigns.isLoading) return <Loading />;
  if (!campaign) return <div style={{ padding: 40, fontFamily: "Inter, system-ui" }}>No campaign yet — run setup first.</div>;

  function renderPage() {
    switch (page) {
      case "overview":
        if (strategy.isLoading) return <Loading />; if (strategy.error) return <ErrorMsg error={strategy.error} />;
        return (<><PageTitle title="Overview" sub={role === "candidate" ? "Where the campaign stands today." : "Your command view of the seat."} />
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <TallyHero s={strategy.data} />
            <div className="grid gap-5" style={{ gridTemplateColumns: "minmax(0,1.7fr) minmax(0,1fr)" }}>
              <UnitRegister units={strategy.data.units} readOnly={role === "candidate"} onAssign={() => setModal({ type: "mobilizer" })} />
              <StrategyPanel notes={strategy.data.notes} dark />
            </div>
          </div></>);
      case "units":
        if (strategy.isLoading) return <Loading />; if (strategy.error) return <ErrorMsg error={strategy.error} />;
        return (<><PageTitle title={role === "candidate" ? "Ward performance" : "Wards"} sub="Win number, progress and coverage per unit." /><UnitRegister units={strategy.data.units} readOnly={role === "candidate"} onAssign={() => setModal({ type: "mobilizer" })} /></>);
      case "strategy":
        if (strategy.isLoading) return <Loading />; if (strategy.error) return <ErrorMsg error={strategy.error} />;
        return (<><PageTitle title="Strategy read" sub="Your next moves, computed from your own data." /><StrategyPanel notes={strategy.data.notes} /></>);
      case "targets": return <TargetsView campaignId={campaignId} />;
      case "mobilizers": return <MobilizersView campaignId={campaignId} onAdd={() => setModal({ type: "mobilizer" })} />;
      case "supporters": return <SupportersView campaignId={campaignId} />;
      case "events":
      case "myevents":
        if (events.isLoading) return <Loading />; if (events.error) return <ErrorMsg error={events.error} />;
        return (<><PageTitle title={page === "myevents" ? "My events" : "Events"} sub="Rallies and meetings, with mobilization counts." action={role !== "candidate" ? <Btn primary onClick={() => setModal({ type: "event" })}>Schedule event</Btn> : null} /><EventList events={events.data || []} showActions={role !== "candidate"} onRecord={(e) => setModal({ type: "record", event: e })} /></>);
      case "register": return (<><PageTitle title="Register a supporter" sub="Quick capture in the field." /><RegisterSupporterForm campaignId={campaignId} wardOptions={wardOptions} /></>);
      case "mysupporters": return <SupportersView campaignId={campaignId} />;
      default: return null;
    }
  }

  return (
    <div style={{ background: C.paper, color: C.ink, minHeight: "100%", fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif" }}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap'); *{box-sizing:border-box}`}</style>

      <div style={{ background: C.railBg, color: "#fff", padding: "10px 18px" }}>
        <div className="mx-auto flex flex-wrap items-center justify-between gap-3" style={{ maxWidth: 1200 }}>
          <div className="flex items-center gap-3"><div style={{ ...DISPLAY, fontSize: 18, fontWeight: 700 }}>MZIGO<span style={{ color: C.green }}>·</span>CRM</div><div style={{ fontSize: 12, color: "#8E968F" }}>{campaign.title}</div></div>
          <div className="flex items-center gap-3" style={{ fontSize: 12 }}><span style={{ color: "#8E968F" }}>{user?.full_name || user?.username} · {ROLE_LABEL[role]}</span><button onClick={logout} style={{ background: "transparent", border: "1px solid #2A322D", color: "#C7CDC8", borderRadius: 8, padding: "5px 10px", cursor: "pointer" }}>Sign out</button></div>
        </div>
      </div>

      <div className="mx-auto" style={{ maxWidth: 1200, display: "flex" }}>
        <div style={{ width: 210, flexShrink: 0, borderRight: `1px solid ${C.line}`, padding: "20px 12px" }}>
          <div style={{ padding: "0 8px 10px", ...DISPLAY, fontSize: 12, letterSpacing: 1.5, color: C.sub, fontWeight: 600 }}>{ROLE_LABEL[role].toUpperCase()}</div>
          <div className="flex" style={{ flexDirection: "column", gap: 2 }}>
            {nav.map(([key, label]) => <button key={key} onClick={() => setPage(key)} style={{ textAlign: "left", padding: "9px 12px", borderRadius: 8, fontSize: 13.5, fontWeight: page === key ? 600 : 500, cursor: "pointer", border: "none", background: page === key ? C.ink : "transparent", color: page === key ? "#fff" : C.ink }}>{label}</button>)}
          </div>
        </div>

        <div style={{ flex: 1, minWidth: 0, padding: "24px 20px 48px" }}>
          <div className="flex flex-wrap items-end justify-between gap-2" style={{ marginBottom: 18, paddingBottom: 12, borderBottom: `2px solid ${C.ink}` }}>
            <div style={{ ...DISPLAY, fontSize: 22, fontWeight: 700 }}>{campaign.title}</div>
          </div>
          {renderPage()}
        </div>
      </div>

      {modal?.type === "mobilizer" && <AddMobilizerForm campaignId={campaignId} wardOptions={wardOptions} onClose={() => setModal(null)} />}
      {modal?.type === "event" && <ScheduleEventForm campaignId={campaignId} wardOptions={wardOptions} onClose={() => setModal(null)} />}
      {modal?.type === "record" && <RecordForm event={modal.event} onClose={() => setModal(null)} />}
    </div>
  );
}
