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
import { formatNumber as fmt } from "../lib/format";
import {
  Button,
  FieldLabel,
  SelectField,
} from "./ui";

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
  <FieldLabel className="onboarding-label">{children}</FieldLabel>
);
const Select = (props) => (
  <SelectField {...props} className="onboarding-field" />
);
const Btn = ({ children, onClick, disabled, primary }) => (
  <Button
    onClick={onClick}
    disabled={disabled}
    primary={primary}
    className={`onboarding-button ${
      primary ? "onboarding-button-primary" : "onboarding-button-secondary"
    }`}
  >
    {children}
  </Button>
);

// The units this seat will be worked on, listed before anything is created.
function UnitsPreview({ form }) {
  const { grain, units, isLoading, error } = useUnitsPreview(form);
  const noun = grain === "centre" ? "registration centre" : "ward";
  const registered = units.reduce(
    (total, u) => total + (u.registered_voters || 0),
    0,
  );

  if (isLoading)
    return (
      <div className="onboarding-box onboarding-box-head">
        <span className="onboarding-subtext">Loading the {noun}s…</span>
      </div>
    );
  if (error)
    return (
      <div className="onboarding-box onboarding-box-head">
        <span className="onboarding-error">{error.message}</span>
      </div>
    );

  if (units.length === 0) {
    return (
      <div className="onboarding-box">
        <div className="onboarding-box-head">
          <span className="onboarding-display onboarding-box-title">
            No {noun}s loaded
          </span>
        </div>
        <div className="onboarding-box-message">
          {grain === "centre"
            ? "This ward has no registration centres loaded, so an MCA campaign cannot be set up here until they are."
            : "Nothing was found for this area. Check the selection on the previous step."}
        </div>
      </div>
    );
  }

  return (
    <div className="onboarding-box">
      <div
        className="onboarding-box-head flex flex-wrap items-baseline justify-between gap-2"
      >
        <span className="onboarding-display onboarding-box-title">
          {units.length} {noun}
          {units.length === 1 ? "" : "s"}
        </span>
        <span className="onboarding-box-count">
          {fmt(registered)} registered voters
        </span>
      </div>
      <div className="onboarding-box-table-wrap">
        <table className="onboarding-box-table">
          <tbody>
            {units.map((u, i) => (
              <tr
                key={u.id}
                className={i ? "onboarding-box-row" : undefined}
              >
                <td className="onboarding-box-cell onboarding-box-cell-name">
                  {u.name}
                </td>
                <td
                  className="onboarding-box-cell onboarding-box-cell-count"
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
      <div className="onboarding-subtext">{sub}</div>
      <div className="onboarding-spacer-10" />
      <div className="flex gap-2">
        <div className="onboarding-person-field">
          <Label>First name</Label>
          <input
            className="onboarding-field"
            value={form[key("first")]}
            onChange={(e) => set({ [key("first")]: e.target.value })}
          />
        </div>
        <div className="onboarding-person-field">
          <Label>Last name</Label>
          <input
            className="onboarding-field"
            value={form[key("last")]}
            onChange={(e) => set({ [key("last")]: e.target.value })}
          />
        </div>
      </div>
      <div className="onboarding-spacer-10" />
      <Label>Username</Label>
      <input
        className="onboarding-field"
        value={form[key("username")]}
        onChange={(e) => set({ [key("username")]: e.target.value })}
        placeholder={who === "manager" ? "otieno" : "jane"}
      />
      <div className="onboarding-spacer-10" />
      <Label>Email</Label>
      <input
        type="email"
        className="onboarding-field"
        value={form[key("email")]}
        onChange={(e) => set({ [key("email")]: e.target.value })}
        placeholder="name@example.com"
      />
      <div className="onboarding-spacer-10" />
      <Label>Phone</Label>
      <input
        className="onboarding-field"
        value={form[key("phone")]}
        onChange={(e) => set({ [key("phone")]: e.target.value })}
        placeholder="0712 345678"
      />
      <div className="onboarding-help">
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
    <div className="onboarding-box">
      <div className="onboarding-box-head">
        <span className="onboarding-display onboarding-login-name">
          {login.full_name || login.username}
          {ROLE_NAME[login.role] || ""} signs in with
        </span>
        <span className="onboarding-box-note onboarding-login-note">
          shown once
        </span>
      </div>
      <div className="flex items-center justify-between gap-2 onboarding-login-row">
        <span className="onboarding-login-name">
          {login.username}
        </span>
        <span className="onboarding-login-password">
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

  // success screen (after setup returns)
  if (setup.isSuccess) {
    const s = setup.data.setup;
    return (
      <div className="onboarding-shell">
        <div className="onboarding-card">
          <div className="onboarding-success-kicker">
            THE CAMPAIGN IS SET UP
          </div>
          <div className="onboarding-success-meta">
            Win number across {s.units}{" "}
            {s.grain === "centre" ? "registration centres" : "wards"}:
          </div>
          <div className="onboarding-display onboarding-win-number">
            {Number(s.win_number).toLocaleString()}
          </div>
          <div className="onboarding-success-meta">
            from {Number(s.total_registered).toLocaleString()} registered
            voters, at the county's 2022 turnout.
          </div>
          {s.note && (
            <div className="onboarding-success-note">
              {s.note}
            </div>
          )}
          {setup.data.logins.map((login) => (
            <NewLogin key={login.id} login={login} />
          ))}
          <div className="onboarding-success-action">
            <Btn primary onClick={() => onDone(setup.data)}>
              Back to the console
            </Btn>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="onboarding-shell">
      <div className="onboarding-card">
        <div className="flex items-center justify-between">
          <div className="onboarding-display onboarding-brand">
            MZIGO<span className="onboarding-brand-mark">·</span>CRM
          </div>
          <button
            onClick={onCancel}
            className="onboarding-cancel"
          >
            Cancel
          </button>
        </div>
        <div className="onboarding-progress">
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
            <div className="onboarding-actions-right">
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
              <div className="onboarding-error">
                The manager needs a different username from the aspirant.
              </div>
            )}
            <div className="onboarding-actions">
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
              className="onboarding-field"
              value={form.title}
              onChange={(e) => set({ title: e.target.value })}
              placeholder="e.g. Jane for Roysambu"
              autoFocus
            />
            <div className="onboarding-spacer-14" />
            <Label>Election date</Label>
            <input
              type="date"
              className="onboarding-field"
              value={form.election_date}
              onChange={(e) => set({ election_date: e.target.value })}
            />
            <div
              className={`onboarding-actions ${
                step === 0 ? "onboarding-actions-end" : ""
              }`}
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
            <div className="onboarding-office-list">
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
                  className={`onboarding-office ${
                    form.seat === o.key ? "onboarding-office-selected" : ""
                  }`}
                >
                  <div className="onboarding-display onboarding-office-title">
                    {o.label}
                  </div>
                  <div className="onboarding-office-subtitle">
                    {o.sub}
                  </div>
                </button>
              ))}
            </div>
            <div className="onboarding-actions">
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
                <div className="onboarding-spacer-12" />
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
                <div className="onboarding-spacer-12" />
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
            <div className="onboarding-actions">
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
            <div className="onboarding-review-notice">
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
            <div className="onboarding-review-copy">
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
              <div className="onboarding-review-error">
                {setup.error.message}
              </div>
            )}
            <div className="onboarding-actions">
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
