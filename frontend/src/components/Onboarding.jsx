// The console's new-campaign wizard: the aspirant, an optional manager, the
// seat and its area, then a review that builds every target and both logins.
import React, { useState } from "react";
import {
  useCounties,
  useConstituencies,
  useWardsIn,
  useUnitsPreview,
  useAdminCreateCampaign,
} from "../api/hooks";

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

// Each seat and the area it is fought over; the county seats share one area.
const OFFICES = [
  {
    key: "mca",
    level: "ward",
    label: "MCA",
    sub: "Member of County Assembly — a ward seat",
  },
  {
    key: "mp",
    level: "constituency",
    label: "MP",
    sub: "Member of Parliament — a constituency seat",
  },
  {
    key: "governor",
    level: "county",
    label: "Governor",
    sub: "A county-wide seat",
  },
  {
    key: "senator",
    level: "county",
    label: "Senator",
    sub: "A county-wide seat",
  },
  {
    key: "women_rep",
    level: "county",
    label: "Women Rep",
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
          Loading the {noun}s…
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
            ? "This ward has no registration centres loaded, so an MCA campaign cannot be set up here until they are."
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

// The server takes `^[A-Za-z0-9._-]+$`, 3 to 150 characters. Mirroring it here
// refuses a username on the step that asks for it rather than four steps later.
const USERNAME = /^[A-Za-z0-9._-]+$/;

function usableUsername(value) {
  const name = value.trim();
  return name.length >= 3 && name.length <= 150 && USERNAME.test(name);
}

// Every login belongs to one campaign, so each person here is somebody new.
function PersonStep({ who, title, sub, form, set }) {
  const key = (field) => `${who}_${field}`;
  return (
    <>
      <Label>{title}</Label>
      <div style={{ fontSize: 12.5, color: C.sub, marginTop: 4 }}>{sub}</div>
      <div style={{ height: 10 }} />
      <div className="flex gap-2">
        <div style={{ flex: 1 }}>
          <Label>First name</Label>
          <input
            style={FIELD}
            value={form[key("first")]}
            onChange={(e) => set({ [key("first")]: e.target.value })}
          />
        </div>
        <div style={{ flex: 1 }}>
          <Label>Last name</Label>
          <input
            style={FIELD}
            value={form[key("last")]}
            onChange={(e) => set({ [key("last")]: e.target.value })}
          />
        </div>
      </div>
      <div style={{ height: 10 }} />
      <Label>Username</Label>
      <input
        style={FIELD}
        value={form[key("username")]}
        onChange={(e) => set({ [key("username")]: e.target.value })}
        placeholder={who === "manager" ? "otieno" : "jane"}
      />
      <div style={{ height: 10 }} />
      <Label>Email</Label>
      <input
        type="email"
        style={FIELD}
        value={form[key("email")]}
        onChange={(e) => set({ [key("email")]: e.target.value })}
        placeholder="name@example.com"
      />
      <div style={{ height: 10 }} />
      <Label>Phone</Label>
      <input
        style={FIELD}
        value={form[key("phone")]}
        onChange={(e) => set({ [key("phone")]: e.target.value })}
        placeholder="0712 345678"
      />
      <div style={{ fontSize: 12, color: C.sub, marginTop: 8 }}>
        They get a login for this campaign only, and its password is shown once
        at the end. Write it down: nothing is emailed yet, so the address is
        only kept on record.
      </div>
    </>
  );
}

const ROLE_NAME = { candidate: " (aspirant)", manager: " (manager)" };

// A new login, shown once after setup.
function NewLogin({ login }) {
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
          {login.full_name || login.username}
          {ROLE_NAME[login.role] || ""} signs in with
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

export default function Onboarding({ onDone, onCancel, onLogin }) {
  const [step, setStep] = useState(0);
  const [form, setForm] = useState({
    title: "",
    election_date: "2027-08-10",
    seat: "",
    office_level: "",
    county: "",
    constituency: "",
    ward: "",
    aspirant_first: "",
    aspirant_last: "",
    aspirant_username: "",
    aspirant_email: "",
    aspirant_phone: "",
    manager_first: "",
    manager_last: "",
    manager_username: "",
    manager_email: "",
    manager_phone: "",
  });
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  const steps = ["aspirant", "manager", "basics", "office", "area", "review"];
  const at = steps[step];
  const newAspirantName = [form.aspirant_first, form.aspirant_last]
    .map((part) => part.trim())
    .filter(Boolean)
    .join(" ");

  const aspirantReady = usableUsername(form.aspirant_username);
  const hasManager = form.manager_username.trim() !== "";
  const managerTyped = ["first", "last", "email", "phone"].some(
    (field) => form[`manager_${field}`].trim() !== "",
  );
  const sameUsername =
    hasManager &&
    form.manager_username.trim().toLowerCase() ===
      form.aspirant_username.trim().toLowerCase();
  const managerReady = hasManager
    ? usableUsername(form.manager_username) && !sameUsername
    : !managerTyped;
  const person = (who) => ({
    username: form[`${who}_username`].trim().toLowerCase(),
    first_name: form[`${who}_first`].trim(),
    last_name: form[`${who}_last`].trim(),
    phone: form[`${who}_phone`].trim(),
    email: form[`${who}_email`].trim(),
  });

  const counties = useCounties();
  const constituencies = useConstituencies(form.county);
  const wards = useWardsIn(form.constituency);
  const setup = useAdminCreateCampaign({ onPassword: onLogin });

  const needConstituency =
    form.office_level === "constituency" || form.office_level === "ward";
  const needWard = form.office_level === "ward";
  const preview = useUnitsPreview(form);
  // An MCA seat is targeted per centre, so a ward with none cannot be set up.
  const noCentres =
    preview.grain === "centre" &&
    !preview.isLoading &&
    preview.units.length === 0;
  const areaReady =
    form.county &&
    (!needConstituency || form.constituency) &&
    (!needWard || form.ward);

  const create = () => {
    const payload = {
      title: form.title,
      seat: form.seat,
      election_date: form.election_date,
      aspirant: person("aspirant"),
      manager: hasManager ? person("manager") : null,
    };
    if (form.office_level === "county") payload.county = form.county;
    if (form.office_level === "constituency")
      payload.constituency = form.constituency;
    if (form.office_level === "ward") payload.ward = form.ward;
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
            THE CAMPAIGN IS SET UP
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
          {setup.data.logins.map((login) => (
            <NewLogin key={login.id} login={login} />
          ))}
          <div style={{ marginTop: 20 }}>
            <Btn primary onClick={() => onDone(setup.data)}>
              Back to the console
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
        <div className="flex items-center justify-between">
          <div style={{ ...DISPLAY, fontSize: 22, fontWeight: 700 }}>
            MZIGO<span style={{ color: C.green }}>·</span>CRM
          </div>
          <button
            onClick={onCancel}
            style={{
              background: "transparent",
              border: `1px solid ${C.line}`,
              color: C.sub,
              borderRadius: 8,
              padding: "5px 10px",
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            Cancel
          </button>
        </div>
        <div style={{ fontSize: 12.5, color: C.sub, marginBottom: 16 }}>
          New campaign · step {step + 1} of {steps.length}
        </div>

        {at === "aspirant" && (
          <>
            <PersonStep
              who="aspirant"
              title="Who is the aspirant?"
              sub="The campaign belongs to them."
              form={form}
              set={set}
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

        {at === "manager" && (
          <>
            <PersonStep
              who="manager"
              title="Who manages it? (optional)"
              sub="Leave every field blank to add the manager later."
              form={form}
              set={set}
            />
            {sameUsername && (
              <div style={{ color: C.red, fontSize: 12.5, marginTop: 8 }}>
                The manager needs a different username from the aspirant.
              </div>
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
                disabled={!managerReady}
                onClick={() => setStep(step + 1)}
              >
                {hasManager || managerTyped ? "Next" : "Skip"}
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
            <Label>Which seat is this campaign for?</Label>
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
                    o.key !== form.seat &&
                    set({
                      seat: o.key,
                      office_level: o.level,
                      ...(o.level !== form.office_level && {
                        constituency: "",
                        ward: "",
                      }),
                    })
                  }
                  style={{
                    textAlign: "left",
                    padding: "12px 14px",
                    borderRadius: 10,
                    cursor: "pointer",
                    border: `1px solid ${form.seat === o.key ? C.ink : C.line}`,
                    background: form.seat === o.key ? C.ink : C.panel,
                    color: form.seat === o.key ? "#fff" : C.ink,
                  }}
                >
                  <div style={{ ...DISPLAY, fontSize: 16, fontWeight: 600 }}>
                    {o.label}
                  </div>
                  <div
                    style={{
                      fontSize: 12,
                      color: form.seat === o.key ? "#C7CDC8" : C.sub,
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
                disabled={!form.seat}
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
              This creates a new login for{" "}
              <b>{newAspirantName || form.aspirant_username}</b>
              {hasManager && (
                <>
                  {" "}
                  and one for their manager <b>{form.manager_username}</b>
                </>
              )}
              , and the campaign belongs to the aspirant. Passwords are shown
              once on the next screen.
            </div>
            <div style={{ fontSize: 14, lineHeight: 1.6 }}>
              This sets up <b>{form.title}</b> for a{" "}
              <b>{OFFICES.find((o) => o.key === form.seat)?.label}</b> seat.
              We'll pull in every{" "}
              {form.office_level === "ward"
                ? "registration centre in its ward"
                : "ward in its area"}
              , set each turnout to its county's 2022 figure, and compute the
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
              <Btn
                primary
                onClick={create}
                disabled={setup.isPending || noCentres}
              >
                {setup.isPending ? "Building…" : "Create campaign"}
              </Btn>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
