// src/components/Onboarding.jsx
// Four steps: basics -> office level -> area (cascading) -> review & create.
// On create it calls /campaigns/setup/, which builds every target and returns
// the win number, then hands the campaign back to the app to show the dashboard.
import React, { useState } from "react";
import {
  useCounties,
  useConstituencies,
  useWardsIn,
  useSetupCampaign,
  useUnitsPreview,
  useCreateUser,
  useWardsInCounty,
  useTeam,
} from "../api/hooks";
import { useAuth } from "../store/auth";

const C = {
  ink: "#171C1F",
  paper: "#E9EBE6",
  panel: "#FFFFFF",
  green: "#0B6B3A",
  red: "#B4231F",
  amber: "#B9791A",
  line: "#D7DBD4",
  sub: "#5C655F",
};
const DISPLAY = { fontFamily: "Oswald, Impact, sans-serif" };
const FIELD = {
  width: "100%",
  padding: "10px 12px",
  borderRadius: 8,
  border: `1px solid ${C.line}`,
  fontSize: 14,
  marginTop: 6,
  background: C.panel,
  fontFamily: "inherit",
};

const OFFICES = [
  { key: "ward", label: "MCA", sub: "Member of County Assembly — a ward seat" },
  {
    key: "constituency",
    label: "MP",
    sub: "Member of Parliament — a constituency seat",
  },
  {
    key: "county",
    label: "Governor / Senator / Woman Rep",
    sub: "A county-wide seat",
  },
];

const Label = ({ children }) => (
  <div style={{ fontSize: 13, fontWeight: 600 }}>{children}</div>
);
const Select = ({ value, onChange, disabled, children }) => (
  <select
    value={value || ""}
    onChange={(e) => onChange(e.target.value)}
    disabled={disabled}
    style={{ ...FIELD, opacity: disabled ? 0.5 : 1 }}
  >
    {children}
  </select>
);

const Btn = ({ children, onClick, disabled, primary }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    style={{
      padding: "10px 18px",
      borderRadius: 8,
      border: primary ? "none" : `1px solid ${C.line}`,
      background: disabled ? C.line : primary ? C.green : C.panel,
      color: primary ? "#fff" : C.ink,
      ...DISPLAY,
      fontWeight: 600,
      fontSize: 14,
      cursor: disabled ? "default" : "pointer",
    }}
  >
    {children}
  </button>
);

const fmt = (n) => Number(n || 0).toLocaleString();

// The units this seat will be worked on, listed before anything is created.
function UnitsPreview({ form }) {
  const { grain, units, isLoading, error } = useUnitsPreview(form);
  const noun = grain === "centre" ? "registration centre" : "ward";
  const registered = units.reduce(
    (total, u) => total + (u.registered_voters || 0),
    0,
  );

  const box = {
    marginTop: 16,
    border: `1px solid ${C.line}`,
    borderRadius: 10,
    overflow: "hidden",
  };
  const head = {
    padding: "10px 14px",
    background: C.paper,
    borderBottom: `1px solid ${C.line}`,
  };

  if (isLoading)
    return (
      <div style={{ ...box, ...head }}>
        <span style={{ fontSize: 13, color: C.sub }}>
          Loading your {noun}s…
        </span>
      </div>
    );
  if (error)
    return (
      <div style={{ ...box, ...head }}>
        <span style={{ fontSize: 13, color: C.red }}>{error.message}</span>
      </div>
    );

  if (units.length === 0) {
    return (
      <div style={box}>
        <div style={head}>
          <span style={{ ...DISPLAY, fontSize: 14, fontWeight: 600 }}>
            No {noun}s loaded
          </span>
        </div>
        <div
          style={{
            padding: "12px 14px",
            fontSize: 12.5,
            color: C.amber,
            lineHeight: 1.5,
          }}
        >
          {grain === "centre"
            ? "This ward has no registration centres yet. The campaign will be created, but it will have nothing to target until they are imported."
            : "Nothing was found for this area. Check the selection on the previous step."}
        </div>
      </div>
    );
  }

  return (
    <div style={box}>
      <div
        className="flex flex-wrap items-baseline justify-between gap-2"
        style={head}
      >
        <span style={{ ...DISPLAY, fontSize: 14, fontWeight: 600 }}>
          {units.length} {noun}
          {units.length === 1 ? "" : "s"}
        </span>
        <span style={{ fontSize: 12.5, color: C.sub }}>
          {fmt(registered)} registered voters
        </span>
      </div>
      <div style={{ maxHeight: 190, overflowY: "auto" }}>
        <table
          style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}
        >
          <tbody>
            {units.map((u, i) => (
              <tr
                key={u.id}
                style={i ? { borderTop: `1px solid ${C.line}` } : undefined}
              >
                <td style={{ padding: "9px 14px", fontWeight: 500 }}>
                  {u.name}
                </td>
                <td
                  style={{
                    padding: "9px 14px",
                    textAlign: "right",
                    color: C.sub,
                  }}
                >
                  {u.registered_voters ? fmt(u.registered_voters) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Mobilizer logins, the only team a manager or a candidate adds. The password
// is shown once and never again.
function TeamStep({ campaign, form, viewerIsManager }) {
  const create = useCreateUser();
  const wardsInCounty = useWardsInCounty(
    form.office_level === "county" ? form.county : null,
  );
  const wardsInConstituency = useWardsIn(
    form.office_level === "constituency" ? form.constituency : null,
  );
  const [fields, setFields] = useState({
    username: "",
    first_name: "",
    last_name: "",
    phone: "",
    ward: "",
  });
  const [made, setMade] = useState([]);

  const wards =
    form.office_level === "ward"
      ? [{ id: form.ward, name: "your ward" }]
      : (form.office_level === "county"
          ? wardsInCounty.data
          : wardsInConstituency.data) || [];
  const ward = fields.ward || wards[0]?.id || form.ward;
  const ok = usableUsername(fields.username) && !!ward;

  const set = (patch) => setFields((f) => ({ ...f, ...patch }));
  const add = () =>
    create.mutate(
      {
        username: fields.username.trim().toLowerCase(),
        role: "mobilizer",
        first_name: fields.first_name.trim(),
        last_name: fields.last_name.trim(),
        phone: fields.phone.trim(),
        campaign: campaign.id,
        ward,
      },
      {
        onSuccess: (person) => {
          setMade((m) => [...m, person]);
          setFields({
            username: "",
            first_name: "",
            last_name: "",
            phone: "",
            ward: "",
          });
        },
      },
    );

  return (
    <div
      style={{
        marginTop: 22,
        borderTop: `1px solid ${C.line}`,
        paddingTop: 18,
      }}
    >
      <div style={{ ...DISPLAY, fontSize: 16, fontWeight: 600 }}>
        Add your team
      </div>
      <div style={{ fontSize: 12.5, color: C.sub, marginTop: 2 }}>
        {viewerIsManager
          ? "You run this campaign. Add the mobilizers who work each ward."
          : "You are the candidate. Add the mobilizers who work each ward."}
      </div>

      <div style={{ height: 12 }} />
      <Label>Username</Label>
      <input
        style={FIELD}
        value={fields.username}
        onChange={(e) => set({ username: e.target.value })}
        placeholder="amina"
      />
      <div style={{ height: 10 }} />
      <div className="flex gap-2">
        <div style={{ flex: 1 }}>
          <Label>First name</Label>
          <input
            style={FIELD}
            value={fields.first_name}
            onChange={(e) => set({ first_name: e.target.value })}
          />
        </div>
        <div style={{ flex: 1 }}>
          <Label>Last name</Label>
          <input
            style={FIELD}
            value={fields.last_name}
            onChange={(e) => set({ last_name: e.target.value })}
          />
        </div>
      </div>
      <div style={{ height: 10 }} />
      <Label>Phone</Label>
      <input
        style={FIELD}
        value={fields.phone}
        onChange={(e) => set({ phone: e.target.value })}
        placeholder="0712 345678"
      />

      {wards.length > 1 && (
        <>
          <div style={{ height: 10 }} />
          <Label>Ward</Label>
          <Select value={ward} onChange={(v) => set({ ward: v })}>
            {wards.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </Select>
        </>
      )}

      {create.isError && (
        <div style={{ color: C.red, fontSize: 12.5, marginTop: 8 }}>
          {create.error.message}
        </div>
      )}
      <div style={{ marginTop: 14 }}>
        <Btn onClick={add} disabled={!ok || create.isPending}>
          {create.isPending ? "Adding…" : "Add to the team"}
        </Btn>
      </div>

      {made.length > 0 && <TeamMade made={made} />}
    </div>
  );
}

// The only copy of each password there will be.
function TeamMade({ made }) {
  return (
    <div
      style={{
        marginTop: 16,
        border: `1px solid ${C.line}`,
        borderRadius: 10,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "9px 14px",
          background: C.paper,
          borderBottom: `1px solid ${C.line}`,
        }}
      >
        <span style={{ ...DISPLAY, fontSize: 13, fontWeight: 600 }}>
          Write these down now
        </span>
        <span style={{ fontSize: 12, color: C.amber, marginLeft: 8 }}>
          shown once
        </span>
      </div>
      <table
        style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}
      >
        <tbody>
          {made.map((p, i) => (
            <tr
              key={p.id}
              style={i ? { borderTop: `1px solid ${C.line}` } : undefined}
            >
              <td style={{ padding: "9px 14px", fontWeight: 600 }}>
                {p.username}
                <div style={{ fontSize: 11.5, color: C.sub, fontWeight: 400 }}>
                  Mobilizer · {p.ward_name || ""}
                </div>
              </td>
              <td
                style={{
                  padding: "9px 14px",
                  textAlign: "right",
                  fontFamily: "ui-monospace, monospace",
                  fontSize: 12.5,
                }}
              >
                {p.password}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// A manager sets the campaign up for an aspirant, so it has to say which one.
// Inferring it from whoever filled the form in leaves the campaign owned by its
// manager and invisible to its candidate.
// The server takes `^[A-Za-z0-9._-]+$`, 3 to 150 characters. Mirroring it here
// refuses a username on the step that asks for it rather than four steps later.
const USERNAME = /^[A-Za-z0-9._-]+$/;

function usableUsername(value) {
  const name = value.trim();
  return name.length >= 3 && name.length <= 150 && USERNAME.test(name);
}

function AspirantStep({ form, set, loading, error, aspirants }) {
  if (error)
    return (
      <>
        <Label>Who are you running this campaign for?</Label>
        <div
          style={{ fontSize: 13, color: C.red, marginTop: 8, lineHeight: 1.5 }}
        >
          {error.message}
        </div>
        <div style={{ fontSize: 12.5, color: C.sub, marginTop: 8 }}>
          We could not reach the server, so this step cannot go on. Reload and
          try again.
        </div>
      </>
    );
  if (loading)
    return (
      <>
        <Label>Who are you running this campaign for?</Label>
        <div style={{ fontSize: 13, color: C.sub, marginTop: 8 }}>
          One moment…
        </div>
      </>
    );

  const known = aspirants.filter((a) => a.id !== form.aspirant_existing);

  return (
    <>
      <Label>Who are you running this campaign for?</Label>
      <div style={{ fontSize: 12.5, color: C.sub, marginTop: 4 }}>
        The campaign belongs to them, not to you.
      </div>
      {aspirants.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <Label>An aspirant already here</Label>
          <select
            style={FIELD}
            value={form.aspirant_existing}
            onChange={(e) => set({ aspirant_existing: e.target.value })}
          >
            <option value="">Somebody new…</option>
            {aspirants.map((a) => (
              <option key={a.id} value={a.id}>
                {a.full_name || a.username} ({a.username})
              </option>
            ))}
          </select>
          <div style={{ fontSize: 12, color: C.sub, marginTop: 6 }}>
            {form.aspirant_existing
              ? "They keep the login they already have."
              : `${known.length} already set up. Pick one, or fill the form below.`}
          </div>
        </div>
      )}
      {form.aspirant_existing ? null : (
        <>
          <div style={{ height: 10 }} />
          <div className="flex gap-2">
            <div style={{ flex: 1 }}>
              <Label>First name</Label>
              <input
                style={FIELD}
                value={form.aspirant_first}
                onChange={(e) => set({ aspirant_first: e.target.value })}
              />
            </div>
            <div style={{ flex: 1 }}>
              <Label>Last name</Label>
              <input
                style={FIELD}
                value={form.aspirant_last}
                onChange={(e) => set({ aspirant_last: e.target.value })}
              />
            </div>
          </div>
          <div style={{ height: 10 }} />
          <Label>Username</Label>
          <input
            style={FIELD}
            value={form.aspirant_username}
            onChange={(e) => set({ aspirant_username: e.target.value })}
            placeholder="jane"
          />
          <div style={{ height: 10 }} />
          <Label>Email</Label>
          <input
            type="email"
            style={FIELD}
            value={form.aspirant_email}
            onChange={(e) => set({ aspirant_email: e.target.value })}
            placeholder="jane@example.com"
          />
          <div style={{ height: 10 }} />
          <Label>Phone</Label>
          <input
            style={FIELD}
            value={form.aspirant_phone}
            onChange={(e) => set({ aspirant_phone: e.target.value })}
            placeholder="0712 345678"
          />
          <div style={{ fontSize: 12, color: C.sub, marginTop: 8 }}>
            They get a login, and its password is shown once at the end. Write
            it down: nothing is emailed yet, so the address is only kept on
            record.
          </div>
        </>
      )}
    </>
  );
}

// The aspirant's login, shown once after setup.
function CandidateLogin({ login }) {
  return (
    <div
      style={{
        marginTop: 16,
        border: `1px solid ${C.line}`,
        borderRadius: 10,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "9px 14px",
          background: C.paper,
          borderBottom: `1px solid ${C.line}`,
        }}
      >
        <span style={{ ...DISPLAY, fontSize: 13, fontWeight: 600 }}>
          {login.full_name || login.username} signs in with
        </span>
        <span style={{ fontSize: 12, color: C.amber, marginLeft: 8 }}>
          shown once
        </span>
      </div>
      <div
        className="flex items-center justify-between gap-2"
        style={{ padding: "10px 14px" }}
      >
        <span style={{ fontWeight: 600, fontSize: 13.5 }}>
          {login.username}
        </span>
        <span style={{ fontFamily: "ui-monospace, monospace", fontSize: 13 }}>
          {login.password}
        </span>
      </div>
    </div>
  );
}

export default function Onboarding({ onDone }) {
  const role = useAuth((s) => s.user?.role);
  const forAspirant = role === "manager";
  const [step, setStep] = useState(0);
  const [form, setForm] = useState({
    title: "",
    election_date: "2027-08-10",
    office_level: "",
    county: "",
    constituency: "",
    ward: "",
    aspirant_first: "",
    aspirant_last: "",
    aspirant_existing: "",
    aspirant_username: "",
    aspirant_email: "",
    aspirant_phone: "",
  });
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  // A manager names the aspirant first, so their flow has one more step.
  const steps = forAspirant
    ? ["aspirant", "basics", "office", "area", "review"]
    : ["basics", "office", "area", "review"];
  const at = steps[step];
  // The aspirants this manager already set up, so a second campaign for one of
  // them reuses their login instead of colliding with the username.
  const aspirants = useTeam("candidate", forAspirant);
  const chosen = (aspirants.data || []).find(
    (a) => a.id === form.aspirant_existing,
  );
  const chosenAspirantName = chosen?.full_name || chosen?.username || "them";
  const newAspirantName = [form.aspirant_first, form.aspirant_last]
    .map((part) => part.trim())
    .filter(Boolean)
    .join(" ");

  const usernameOk = usableUsername(form.aspirant_username);
  const aspirantReady =
    !forAspirant ||
    (!aspirants.isLoading &&
      !aspirants.error &&
      (Boolean(form.aspirant_existing) || usernameOk));

  const counties = useCounties();
  const constituencies = useConstituencies(form.county);
  const wards = useWardsIn(form.constituency);
  const setup = useSetupCampaign();

  const needConstituency =
    form.office_level === "constituency" || form.office_level === "ward";
  const needWard = form.office_level === "ward";
  const areaReady =
    form.county &&
    (!needConstituency || form.constituency) &&
    (!needWard || form.ward);

  const create = () => {
    const payload = {
      title: form.title,
      office_level: form.office_level,
      election_date: form.election_date,
    };
    if (form.office_level === "county") payload.county = form.county;
    if (form.office_level === "constituency")
      payload.constituency = form.constituency;
    if (form.office_level === "ward") payload.ward = form.ward;
    if (forAspirant && form.aspirant_existing) {
      payload.candidate = form.aspirant_existing;
    } else if (forAspirant) {
      payload.new_candidate = {
        username: form.aspirant_username.trim().toLowerCase(),
        first_name: form.aspirant_first.trim(),
        last_name: form.aspirant_last.trim(),
        phone: form.aspirant_phone.trim(),
        email: form.aspirant_email.trim(),
      };
    }
    setup.mutate(payload);
  };

  const wrap = {
    minHeight: "100vh",
    background: C.paper,
    color: C.ink,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: 16,
    fontFamily: "Inter, system-ui, sans-serif",
  };
  const card = {
    width: "100%",
    maxWidth: 460,
    background: C.panel,
    border: `1px solid ${C.line}`,
    borderRadius: 14,
    padding: 24,
  };

  // success screen (after setup returns)
  if (setup.isSuccess) {
    const s = setup.data.setup;
    return (
      <div style={wrap}>
        <style>{`@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;600;700&family=Inter:wght@400;500;600&display=swap');`}</style>
        <div style={card}>
          <div
            style={{
              ...DISPLAY,
              fontSize: 13,
              letterSpacing: 1.5,
              color: C.green,
              fontWeight: 600,
            }}
          >
            YOUR CAMPAIGN IS SET UP
          </div>
          <div style={{ fontSize: 13, color: C.sub, marginTop: 4 }}>
            Win number across {s.units}{" "}
            {s.grain === "centre" ? "registration centres" : "wards"}:
          </div>
          <div
            style={{
              ...DISPLAY,
              fontSize: 60,
              fontWeight: 700,
              lineHeight: 1,
              marginTop: 6,
            }}
          >
            {Number(s.win_number).toLocaleString()}
          </div>
          <div style={{ fontSize: 13, color: C.sub, marginTop: 4 }}>
            from {Number(s.total_registered).toLocaleString()} registered
            voters, at the county's 2022 turnout.
          </div>
          {s.note && (
            <div style={{ fontSize: 12.5, color: C.amber, marginTop: 12 }}>
              {s.note}
            </div>
          )}
          {setup.data.candidate_login && (
            <CandidateLogin login={setup.data.candidate_login} />
          )}
          <TeamStep
            campaign={setup.data}
            form={form}
            viewerIsManager={forAspirant}
          />
          <div style={{ marginTop: 20 }}>
            <Btn primary onClick={() => onDone(setup.data)}>
              Go to my dashboard →
            </Btn>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={wrap}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;600;700&family=Inter:wght@400;500;600&display=swap');`}</style>
      <div style={card}>
        <div style={{ ...DISPLAY, fontSize: 22, fontWeight: 700 }}>
          MZIGO<span style={{ color: C.green }}>·</span>CRM
        </div>
        <div style={{ fontSize: 12.5, color: C.sub, marginBottom: 16 }}>
          Set up your campaign · step {step + 1} of {steps.length}
        </div>

        {at === "aspirant" && (
          <>
            <AspirantStep
              form={form}
              set={set}
              loading={aspirants.isLoading}
              error={aspirants.error}
              aspirants={aspirants.data || []}
            />
            <div style={{ marginTop: 20, textAlign: "right" }}>
              <Btn
                primary
                disabled={!aspirantReady}
                onClick={() => setStep(step + 1)}
              >
                Next
              </Btn>
            </div>
          </>
        )}

        {at === "basics" && (
          <>
            <Label>Campaign name</Label>
            <input
              style={FIELD}
              value={form.title}
              onChange={(e) => set({ title: e.target.value })}
              placeholder="e.g. Jane for Roysambu"
              autoFocus
            />
            <div style={{ height: 14 }} />
            <Label>Election date</Label>
            <input
              type="date"
              style={FIELD}
              value={form.election_date}
              onChange={(e) => set({ election_date: e.target.value })}
            />
            <div
              style={{
                marginTop: 20,
                display: "flex",
                justifyContent: step > 0 ? "space-between" : "flex-end",
              }}
            >
              {step > 0 && <Btn onClick={() => setStep(step - 1)}>Back</Btn>}
              <Btn
                primary
                disabled={!form.title.trim()}
                onClick={() => setStep(step + 1)}
              >
                Next
              </Btn>
            </div>
          </>
        )}

        {at === "office" && (
          <>
            <Label>What seat are you running for?</Label>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 8,
                marginTop: 8,
              }}
            >
              {OFFICES.map((o) => (
                <button
                  key={o.key}
                  onClick={() =>
                    // Re-affirming the seat already chosen must not wipe the
                    // area that was picked for it.
                    o.key !== form.office_level &&
                    set({ office_level: o.key, constituency: "", ward: "" })
                  }
                  style={{
                    textAlign: "left",
                    padding: "12px 14px",
                    borderRadius: 10,
                    cursor: "pointer",
                    border: `1px solid ${form.office_level === o.key ? C.ink : C.line}`,
                    background: form.office_level === o.key ? C.ink : C.panel,
                    color: form.office_level === o.key ? "#fff" : C.ink,
                  }}
                >
                  <div style={{ ...DISPLAY, fontSize: 16, fontWeight: 600 }}>
                    {o.label}
                  </div>
                  <div
                    style={{
                      fontSize: 12,
                      color: form.office_level === o.key ? "#C7CDC8" : C.sub,
                    }}
                  >
                    {o.sub}
                  </div>
                </button>
              ))}
            </div>
            <div
              style={{
                marginTop: 20,
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              <Btn onClick={() => setStep(step - 1)}>Back</Btn>
              <Btn
                primary
                disabled={!form.office_level}
                onClick={() => setStep(step + 1)}
              >
                Next
              </Btn>
            </div>
          </>
        )}

        {at === "area" && (
          <>
            <Label>County</Label>
            <Select
              value={form.county}
              onChange={(v) => set({ county: v, constituency: "", ward: "" })}
            >
              <option value="">Select county…</option>
              {(counties.data || []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
            {needConstituency && (
              <>
                <div style={{ height: 12 }} />
                <Label>Constituency</Label>
                <Select
                  value={form.constituency}
                  disabled={!form.county}
                  onChange={(v) => set({ constituency: v, ward: "" })}
                >
                  <option value="">Select constituency…</option>
                  {(constituencies.data || []).map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </Select>
              </>
            )}
            {needWard && (
              <>
                <div style={{ height: 12 }} />
                <Label>Ward</Label>
                <Select
                  value={form.ward}
                  disabled={!form.constituency}
                  onChange={(v) => set({ ward: v })}
                >
                  <option value="">Select ward…</option>
                  {(wards.data || []).map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.name}
                    </option>
                  ))}
                </Select>
              </>
            )}
            <div
              style={{
                marginTop: 20,
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              <Btn onClick={() => setStep(step - 1)}>Back</Btn>
              <Btn
                primary
                disabled={!areaReady}
                onClick={() => setStep(step + 1)}
              >
                Next
              </Btn>
            </div>
          </>
        )}

        {at === "review" && (
          <>
            {forAspirant && (
              <div
                style={{
                  fontSize: 13.5,
                  lineHeight: 1.5,
                  marginBottom: 12,
                  padding: "10px 12px",
                  borderRadius: 10,
                  background: C.paper,
                  border: `1px solid ${C.line}`,
                }}
              >
                {form.aspirant_existing ? (
                  <>
                    The campaign belongs to <b>{chosenAspirantName}</b>, who
                    signs in with the login they already have.
                  </>
                ) : (
                  <>
                    This creates a new login for{" "}
                    <b>{newAspirantName || form.aspirant_username}</b>, and the
                    campaign belongs to them. Their password is shown once on
                    the next screen.
                  </>
                )}
              </div>
            )}
            <div style={{ fontSize: 14, lineHeight: 1.6 }}>
              You're setting up <b>{form.title}</b> for a{" "}
              <b>{OFFICES.find((o) => o.key === form.office_level)?.label}</b>{" "}
              seat. We'll pull in every{" "}
              {form.office_level === "ward"
                ? "registration centre in your ward"
                : "ward in your area"}
              , set each turnout to its county's 2022 figure, and compute your
              win number.
            </div>
            <UnitsPreview form={form} />
            {setup.isError && (
              <div style={{ color: C.red, fontSize: 13, marginTop: 12 }}>
                {setup.error.message}
              </div>
            )}
            <div
              style={{
                marginTop: 20,
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              <Btn onClick={() => setStep(step - 1)} disabled={setup.isPending}>
                Back
              </Btn>
              <Btn primary onClick={create} disabled={setup.isPending}>
                {setup.isPending ? "Building…" : "Create campaign"}
              </Btn>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
