// src/components/Onboarding.jsx
// Four steps: basics -> office level -> area (cascading) -> review & create.
// On create it calls /campaigns/setup/, which builds every target and returns
// the win number, then hands the campaign back to the app to show the dashboard.
import React, { useState } from "react";
import { useCounties, useConstituencies, useWardsIn, useSetupCampaign } from "../api/hooks";

const C = { ink: "#171C1F", paper: "#E9EBE6", panel: "#FFFFFF", green: "#0B6B3A", red: "#B4231F", amber: "#B9791A", line: "#D7DBD4", sub: "#5C655F" };
const DISPLAY = { fontFamily: "Oswald, Impact, sans-serif" };
const FIELD = { width: "100%", padding: "10px 12px", borderRadius: 8, border: `1px solid ${C.line}`, fontSize: 14, marginTop: 6, background: C.panel, fontFamily: "inherit" };

const OFFICES = [
  { key: "ward", label: "MCA", sub: "Member of County Assembly — a ward seat" },
  { key: "constituency", label: "MP", sub: "Member of Parliament — a constituency seat" },
  { key: "county", label: "Governor / Senator / Woman Rep", sub: "A county-wide seat" },
];

const Label = ({ children }) => <div style={{ fontSize: 13, fontWeight: 600 }}>{children}</div>;
const Select = ({ value, onChange, disabled, children }) => (
  <select value={value || ""} onChange={(e) => onChange(e.target.value)} disabled={disabled} style={{ ...FIELD, opacity: disabled ? 0.5 : 1 }}>{children}</select>
);

export default function Onboarding({ onDone }) {
  const [step, setStep] = useState(0);
  const [form, setForm] = useState({ title: "", election_date: "2027-08-10", office_level: "", county: "", constituency: "", ward: "" });
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  const counties = useCounties();
  const constituencies = useConstituencies(form.county);
  const wards = useWardsIn(form.constituency);
  const setup = useSetupCampaign();

  const needConstituency = form.office_level === "constituency" || form.office_level === "ward";
  const needWard = form.office_level === "ward";
  const areaReady = form.county && (!needConstituency || form.constituency) && (!needWard || form.ward);

  const create = () => {
    const payload = { title: form.title, office_level: form.office_level, election_date: form.election_date };
    if (form.office_level === "county") payload.county = form.county;
    if (form.office_level === "constituency") payload.constituency = form.constituency;
    if (form.office_level === "ward") payload.ward = form.ward;
    setup.mutate(payload);
  };

  const wrap = { minHeight: "100vh", background: C.paper, color: C.ink, display: "flex", alignItems: "center", justifyContent: "center", padding: 16, fontFamily: "Inter, system-ui, sans-serif" };
  const card = { width: "100%", maxWidth: 460, background: C.panel, border: `1px solid ${C.line}`, borderRadius: 14, padding: 24 };
  const Btn = ({ children, onClick, disabled, primary }) => (
    <button onClick={onClick} disabled={disabled} style={{ padding: "10px 18px", borderRadius: 8, border: primary ? "none" : `1px solid ${C.line}`, background: disabled ? C.line : primary ? C.green : C.panel, color: primary ? "#fff" : C.ink, ...DISPLAY, fontWeight: 600, fontSize: 14, cursor: disabled ? "default" : "pointer" }}>{children}</button>
  );

  // success screen (after setup returns)
  if (setup.isSuccess) {
    const s = setup.data.setup;
    return (
      <div style={wrap}>
        <style>{`@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;600;700&family=Inter:wght@400;500;600&display=swap');`}</style>
        <div style={card}>
          <div style={{ ...DISPLAY, fontSize: 13, letterSpacing: 1.5, color: C.green, fontWeight: 600 }}>YOUR CAMPAIGN IS SET UP</div>
          <div style={{ fontSize: 13, color: C.sub, marginTop: 4 }}>Win number across {s.units} {s.grain === "polling_station" ? "polling stations" : "wards"}:</div>
          <div style={{ ...DISPLAY, fontSize: 60, fontWeight: 700, lineHeight: 1, marginTop: 6 }}>{Number(s.win_number).toLocaleString()}</div>
          <div style={{ fontSize: 13, color: C.sub, marginTop: 4 }}>from {Number(s.total_registered).toLocaleString()} registered voters, at the county's 2022 turnout.</div>
          {s.note && <div style={{ fontSize: 12.5, color: C.amber, marginTop: 12 }}>{s.note}</div>}
          <div style={{ marginTop: 20 }}><Btn primary onClick={() => onDone(setup.data)}>Go to my dashboard →</Btn></div>
        </div>
      </div>
    );
  }

  return (
    <div style={wrap}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;600;700&family=Inter:wght@400;500;600&display=swap');`}</style>
      <div style={card}>
        <div style={{ ...DISPLAY, fontSize: 22, fontWeight: 700 }}>MZIGO<span style={{ color: C.green }}>·</span>CRM</div>
        <div style={{ fontSize: 12.5, color: C.sub, marginBottom: 16 }}>Set up your campaign · step {Math.min(step + 1, 4)} of 4</div>

        {step === 0 && (
          <>
            <Label>Campaign name</Label>
            <input style={FIELD} value={form.title} onChange={(e) => set({ title: e.target.value })} placeholder="e.g. Jane for Roysambu" autoFocus />
            <div style={{ height: 14 }} />
            <Label>Election date</Label>
            <input type="date" style={FIELD} value={form.election_date} onChange={(e) => set({ election_date: e.target.value })} />
            <div style={{ marginTop: 20, textAlign: "right" }}><Btn primary disabled={!form.title.trim()} onClick={() => setStep(1)}>Next</Btn></div>
          </>
        )}

        {step === 1 && (
          <>
            <Label>What seat are you running for?</Label>
            <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
              {OFFICES.map((o) => (
                <button key={o.key} onClick={() => set({ office_level: o.key, constituency: "", ward: "" })}
                  style={{ textAlign: "left", padding: "12px 14px", borderRadius: 10, cursor: "pointer",
                    border: `1px solid ${form.office_level === o.key ? C.ink : C.line}`, background: form.office_level === o.key ? C.ink : C.panel, color: form.office_level === o.key ? "#fff" : C.ink }}>
                  <div style={{ ...DISPLAY, fontSize: 16, fontWeight: 600 }}>{o.label}</div>
                  <div style={{ fontSize: 12, color: form.office_level === o.key ? "#C7CDC8" : C.sub }}>{o.sub}</div>
                </button>
              ))}
            </div>
            <div style={{ marginTop: 20, display: "flex", justifyContent: "space-between" }}><Btn onClick={() => setStep(0)}>Back</Btn><Btn primary disabled={!form.office_level} onClick={() => setStep(2)}>Next</Btn></div>
          </>
        )}

        {step === 2 && (
          <>
            <Label>County</Label>
            <Select value={form.county} onChange={(v) => set({ county: v, constituency: "", ward: "" })}>
              <option value="">Select county…</option>
              {(counties.data || []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
            {needConstituency && (
              <>
                <div style={{ height: 12 }} /><Label>Constituency</Label>
                <Select value={form.constituency} disabled={!form.county} onChange={(v) => set({ constituency: v, ward: "" })}>
                  <option value="">Select constituency…</option>
                  {(constituencies.data || []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </Select>
              </>
            )}
            {needWard && (
              <>
                <div style={{ height: 12 }} /><Label>Ward</Label>
                <Select value={form.ward} disabled={!form.constituency} onChange={(v) => set({ ward: v })}>
                  <option value="">Select ward…</option>
                  {(wards.data || []).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
                </Select>
              </>
            )}
            <div style={{ marginTop: 20, display: "flex", justifyContent: "space-between" }}><Btn onClick={() => setStep(1)}>Back</Btn><Btn primary disabled={!areaReady} onClick={() => setStep(3)}>Next</Btn></div>
          </>
        )}

        {step === 3 && (
          <>
            <div style={{ fontSize: 14, lineHeight: 1.6 }}>
              You're setting up <b>{form.title}</b> for a <b>{OFFICES.find((o) => o.key === form.office_level)?.label}</b> seat.
              We'll pull in every {form.office_level === "ward" ? "polling station in your ward" : "ward in your area"},
              set each turnout to its county's 2022 figure, and compute your win number.
            </div>
            {setup.isError && <div style={{ color: C.red, fontSize: 13, marginTop: 12 }}>{setup.error.message}</div>}
            <div style={{ marginTop: 20, display: "flex", justifyContent: "space-between" }}>
              <Btn onClick={() => setStep(2)} disabled={setup.isPending}>Back</Btn>
              <Btn primary onClick={create} disabled={setup.isPending}>{setup.isPending ? "Building…" : "Create campaign"}</Btn>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
