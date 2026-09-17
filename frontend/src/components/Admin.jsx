// src/components/Admin.jsx
// The console for whoever runs the deployment: every campaign on it, every
// login, and the few repairs that cannot be done from inside a campaign.
// Shown only to a superuser; every route it calls checks the flag again.
import React, { useState } from "react";
import {
  useAdminOverview,
  useAdminUsers,
  useAddMember,
  useCreateLogin,
  useDeleteCampaign,
  useRenameCampaign,
  useRemoveMember,
  useResetPassword,
  useSetActive,
} from "../api/hooks";
import { useAuth } from "../store/auth";

const C = {
  ink: "#171C1F",
  paper: "#E9EBE6",
  panel: "#FFFFFF",
  green: "#0B6B3A",
  greenSoft: "#E1EEE7",
  red: "#B4231F",
  redSoft: "#F6E3E1",
  amber: "#B9791A",
  line: "#D7DBD4",
  sub: "#5C655F",
};
const DISPLAY = { fontFamily: "Oswald, Impact, sans-serif" };
const FIELD = {
  padding: "8px 10px",
  borderRadius: 8,
  border: `1px solid ${C.line}`,
  fontSize: 13,
  background: C.panel,
  fontFamily: "inherit",
};
const fmt = (n) => Number(n || 0).toLocaleString();

const Card = ({ children, pad = 18, style }) => (
  <div
    style={{
      background: C.panel,
      border: `1px solid ${C.line}`,
      borderRadius: 14,
      padding: pad,
      ...style,
    }}
  >
    {children}
  </div>
);

const Btn = ({ children, onClick, disabled, tone }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    style={{
      padding: "6px 12px",
      borderRadius: 8,
      fontSize: 12.5,
      fontWeight: 600,
      cursor: disabled ? "default" : "pointer",
      border: `1px solid ${disabled ? C.line : tone === "danger" ? C.red : C.line}`,
      background: disabled ? C.paper : C.panel,
      color: disabled ? C.sub : tone === "danger" ? C.red : C.ink,
    }}
  >
    {children}
  </button>
);

const Pill = ({ text, color, soft }) => (
  <span
    style={{
      padding: "1px 8px",
      borderRadius: 999,
      fontSize: 11,
      fontWeight: 600,
      color,
      background: soft,
    }}
  >
    {text}
  </span>
);

// Nothing here can be undone, and the rows are close together, so the
// destructive actions ask first and name who they are about.
function Danger({ label, question, onConfirm, disabled, busy }) {
  const [asking, setAsking] = useState(false);
  if (!asking)
    return (
      <Btn tone="danger" disabled={disabled} onClick={() => setAsking(true)}>
        {busy ? "Working…" : label}
      </Btn>
    );
  return (
    <span
      className="flex flex-wrap items-center gap-2"
      style={{ fontSize: 12.5 }}
    >
      <span style={{ color: C.red }}>{question}</span>
      <Btn
        tone="danger"
        disabled={disabled}
        onClick={() => {
          setAsking(false);
          onConfirm();
        }}
      >
        Yes
      </Btn>
      <Btn onClick={() => setAsking(false)}>Cancel</Btn>
    </span>
  );
}

const ROLE_TONE = {
  candidate: { color: C.green, soft: C.greenSoft },
  manager: { color: C.ink, soft: C.paper },
  mobilizer: { color: C.amber, soft: "#F4EAD6" },
};

function Stat({ label, value }) {
  return (
    <div>
      <div style={{ ...DISPLAY, fontSize: 26, fontWeight: 700, lineHeight: 1 }}>
        {fmt(value)}
      </div>
      <div style={{ fontSize: 12, color: C.sub, marginTop: 3 }}>{label}</div>
    </div>
  );
}

// Passwords come back once. Nothing re-fetches them, so they live here until
// the console is closed.
function Handout({ shown }) {
  if (!shown.length) return null;
  return (
    <Card style={{ marginTop: 16, borderColor: C.amber }}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div style={{ ...DISPLAY, fontSize: 15, fontWeight: 600 }}>
          Write these down now
        </div>
        <span style={{ fontSize: 12, color: C.amber }}>
          shown once, never fetchable again
        </span>
      </div>
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: 13,
          marginTop: 10,
        }}
      >
        <tbody>
          {shown.map((p, i) => (
            <tr
              key={p.username}
              style={i ? { borderTop: `1px solid ${C.line}` } : undefined}
            >
              <td style={{ padding: "7px 0", fontWeight: 600 }}>
                {p.username}
              </td>
              <td
                style={{
                  padding: "7px 0",
                  textAlign: "right",
                  fontFamily: "ui-monospace, monospace",
                }}
              >
                {p.password}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function CampaignCard({ campaign, users }) {
  const remove = useRemoveMember();
  const add = useAddMember();
  const rename = useRenameCampaign();
  const drop = useDeleteCampaign();
  const [renaming, setRenaming] = useState(false);
  const [title, setTitle] = useState(campaign.title);
  const [adding, setAdding] = useState(false);
  const [pick, setPick] = useState("");

  const onIt = new Set(campaign.members.map((m) => m.user_id));
  // A superuser reads every campaign through this console, so putting one on a
  // campaign buys nothing and hides the campaign app from them. A disabled
  // login cannot sign in, so staffing with one leaves the campaign unmanned.
  const available = users.filter(
    (u) => !onIt.has(u.id) && !u.is_superuser && u.is_active,
  );
  const error = remove.error || add.error || rename.error || drop.error;

  return (
    <Card style={{ marginBottom: 14 }}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          {renaming ? (
            <div className="flex flex-wrap items-center gap-2">
              <input
                style={{ ...FIELD, minWidth: 240 }}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                aria-label="Campaign name"
              />
              <Btn
                disabled={!title.trim() || rename.isPending}
                onClick={() =>
                  rename.mutate(
                    { campaign: campaign.id, title: title.trim() },
                    { onSuccess: () => setRenaming(false) },
                  )
                }
              >
                {rename.isPending ? "Saving…" : "Save"}
              </Btn>
              <Btn onClick={() => setRenaming(false)}>Cancel</Btn>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <div style={{ ...DISPLAY, fontSize: 18, fontWeight: 700 }}>
                {campaign.title}
              </div>
              <Btn
                onClick={() => {
                  setTitle(campaign.title);
                  setRenaming(true);
                }}
              >
                Rename
              </Btn>
              <Danger
                label="Delete campaign"
                question={`Delete ${campaign.title}, take its ${fmt(campaign.members.length)} people off it, and delete its ${fmt(campaign.targets)} targets, ${fmt(campaign.mobilizers)} mobilizers, ${fmt(campaign.events)} events and ${fmt(campaign.supporters)} supporters? Their logins stay. This cannot be undone.`}
                busy={drop.isPending}
                disabled={drop.isPending}
                onConfirm={() => drop.mutate({ campaign: campaign.id })}
              />
            </div>
          )}
          <div style={{ fontSize: 12.5, color: C.sub, marginTop: 2 }}>
            {campaign.office_level} · for {campaign.candidate} ·{" "}
            {campaign.election_date || "no election date"}
          </div>
        </div>
        <div className="flex flex-wrap gap-4" style={{ fontSize: 12.5 }}>
          <span>
            <b>{fmt(campaign.targets)}</b> targets
          </span>
          <span>
            <b>{fmt(campaign.mobilizers)}</b> mobilizers
          </span>
          <span>
            <b>{fmt(campaign.events)}</b> events
          </span>
          <span>
            <b>{fmt(campaign.supporters)}</b> supporters
          </span>
          <span>
            <b>{fmt(campaign.votes_committed)}</b> /{" "}
            {fmt(campaign.votes_needed)} votes
          </span>
        </div>
      </div>

      <div
        style={{
          marginTop: 12,
          borderTop: `1px solid ${C.line}`,
          paddingTop: 10,
        }}
      >
        {campaign.members.length === 0 && (
          <div style={{ fontSize: 12.5, color: C.red }}>
            Nobody is on this campaign, so nobody can see it. Add someone below.
          </div>
        )}
        {campaign.members.map((m) => {
          const tone = ROLE_TONE[m.role] || ROLE_TONE.manager;
          return (
            <div
              key={m.user_id}
              className="flex flex-wrap items-center justify-between gap-2"
              style={{ padding: "5px 0", fontSize: 13 }}
            >
              <span>
                <b>{m.username}</b>{" "}
                <span style={{ color: C.sub }}>{m.full_name}</span>{" "}
                <Pill text={m.role} color={tone.color} soft={tone.soft} />
              </span>
              <Danger
                label="Take off"
                question={`Take ${m.username} off ${campaign.title}?`}
                busy={remove.isPending && remove.variables?.user === m.user_id}
                disabled={
                  remove.isPending && remove.variables?.user === m.user_id
                }
                onConfirm={() =>
                  remove.mutate({ campaign: campaign.id, user: m.user_id })
                }
              />
            </div>
          );
        })}
      </div>

      {error && (
        <div style={{ color: C.red, fontSize: 12.5, marginTop: 8 }}>
          {error.message}
        </div>
      )}

      <div style={{ marginTop: 10 }}>
        {adding ? (
          <div className="flex flex-wrap items-center gap-2">
            <select
              style={FIELD}
              value={pick}
              onChange={(e) => setPick(e.target.value)}
            >
              <option value="">Choose a login…</option>
              {available.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.username} ({u.role})
                </option>
              ))}
            </select>
            <span style={{ fontSize: 12.5, color: C.sub }}>
              as {available.find((u) => u.id === pick)?.role || "themselves"}
            </span>
            <Btn
              disabled={!pick || add.isPending}
              onClick={() =>
                add.mutate(
                  { campaign: campaign.id, user: pick },
                  {
                    onSuccess: () => {
                      setAdding(false);
                      setPick("");
                    },
                  },
                )
              }
            >
              {add.isPending ? "Adding…" : "Put them on"}
            </Btn>
            <Btn onClick={() => setAdding(false)}>Cancel</Btn>
          </div>
        ) : (
          <Btn onClick={() => setAdding(true)}>Add somebody</Btn>
        )}
      </div>
    </Card>
  );
}

const BLANK = {
  username: "",
  role: "manager",
  first_name: "",
  last_name: "",
  email: "",
  phone: "",
  campaign: "",
  ward: "",
};

// The server takes `^[A-Za-z0-9._-]+$`, 3 to 150 characters.
const USERNAME = /^[A-Za-z0-9._-]+$/;

const ROLES = [
  ["manager", "Campaign manager"],
  ["candidate", "Aspirant"],
  ["mobilizer", "Mobilizer"],
];

function Field({ label, children }) {
  return (
    <label style={{ display: "block", flex: 1, minWidth: 150 }}>
      <span
        style={{
          fontSize: 11.5,
          color: C.sub,
          display: "block",
          marginBottom: 3,
        }}
      >
        {label}
      </span>
      {children}
    </label>
  );
}

function NewLogin({ campaigns, create }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(BLANK);
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  const chosen = campaigns.find((c) => c.id === form.campaign);
  const isMobilizer = form.role === "mobilizer";
  const isAspirant = form.role === "candidate";
  const name = form.username.trim();
  const ready =
    name.length >= 3 &&
    name.length <= 150 &&
    USERNAME.test(name) &&
    (!isMobilizer || (form.campaign && form.ward));

  if (!open)
    return (
      <div style={{ marginBottom: 12 }}>
        <Btn onClick={() => setOpen(true)}>Add a login</Btn>
      </div>
    );

  const submit = () =>
    create.mutate(
      {
        username: name.toLowerCase(),
        role: form.role,
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        email: form.email.trim(),
        phone: form.phone.trim(),
        campaign: form.campaign || null,
        ward: isMobilizer ? form.ward || null : null,
      },
      {
        onSuccess: () => {
          setForm(BLANK);
          setOpen(false);
        },
      },
    );

  return (
    <Card style={{ marginBottom: 14, borderColor: C.ink }}>
      <div
        style={{ ...DISPLAY, fontSize: 15, fontWeight: 600, marginBottom: 10 }}
      >
        A new login
      </div>

      <div className="flex flex-wrap gap-2">
        <Field label="Username">
          <input
            style={{ ...FIELD, width: "100%" }}
            value={form.username}
            onChange={(e) => set({ username: e.target.value })}
            placeholder="jane.wanjiku"
          />
        </Field>
        <Field label="They are a">
          <select
            style={{ ...FIELD, width: "100%" }}
            value={form.role}
            onChange={(e) =>
              set({ role: e.target.value, campaign: "", ward: "" })
            }
          >
            {ROLES.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <div style={{ height: 10 }} />
      <div className="flex flex-wrap gap-2">
        <Field label="First name">
          <input
            style={{ ...FIELD, width: "100%" }}
            value={form.first_name}
            onChange={(e) => set({ first_name: e.target.value })}
          />
        </Field>
        <Field label="Last name">
          <input
            style={{ ...FIELD, width: "100%" }}
            value={form.last_name}
            onChange={(e) => set({ last_name: e.target.value })}
          />
        </Field>
      </div>

      <div style={{ height: 10 }} />
      <div className="flex flex-wrap gap-2">
        <Field label="Email">
          <input
            type="email"
            style={{ ...FIELD, width: "100%" }}
            value={form.email}
            onChange={(e) => set({ email: e.target.value })}
          />
        </Field>
        <Field label="Phone">
          <input
            style={{ ...FIELD, width: "100%" }}
            value={form.phone}
            onChange={(e) => set({ phone: e.target.value })}
            placeholder="0712 345678"
          />
        </Field>
      </div>

      {!isAspirant && (
        <>
          <div style={{ height: 10 }} />
          <div className="flex flex-wrap gap-2">
            <Field label={isMobilizer ? "Campaign" : "Campaign (optional)"}>
              <select
                style={{ ...FIELD, width: "100%" }}
                value={form.campaign}
                onChange={(e) => set({ campaign: e.target.value, ward: "" })}
              >
                <option value="">On no campaign yet…</option>
                {campaigns.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title}
                  </option>
                ))}
              </select>
            </Field>
            {isMobilizer && (
              <Field label="Ward">
                <select
                  style={{ ...FIELD, width: "100%" }}
                  value={form.ward}
                  onChange={(e) => set({ ward: e.target.value })}
                  disabled={!chosen}
                >
                  <option value="">
                    {chosen ? "Choose a ward…" : "Pick a campaign first"}
                  </option>
                  {(chosen?.wards || []).map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.name}
                    </option>
                  ))}
                </select>
              </Field>
            )}
          </div>
        </>
      )}

      <div
        style={{ fontSize: 12, color: C.sub, marginTop: 10, lineHeight: 1.5 }}
      >
        {isAspirant
          ? "The campaign is set up for them afterwards, and becomes theirs then."
          : isMobilizer
            ? "A mobilizer works one ward, and sees only that ward."
            : "Leave the campaign blank to create the login now and place it later."}{" "}
        Their password is shown once, above. Write it down.
      </div>

      {create.error && (
        <div style={{ color: C.red, fontSize: 12.5, marginTop: 8 }}>
          {create.error.message}
        </div>
      )}

      <div className="flex flex-wrap gap-2" style={{ marginTop: 12 }}>
        <Btn disabled={!ready || create.isPending} onClick={submit}>
          {create.isPending ? "Creating…" : "Create the login"}
        </Btn>
        <Btn
          onClick={() => {
            setForm(BLANK);
            setOpen(false);
          }}
        >
          Cancel
        </Btn>
      </div>
    </Card>
  );
}

function UserRow({ user, me, onReset, resetting, resetError }) {
  const active = useSetActive();
  const tone = ROLE_TONE[user.role] || ROLE_TONE.manager;
  const isMe = user.id === me;
  const error = resetError || active.error?.message;

  return (
    <div
      data-testid={`login-${user.username}`}
      style={{
        borderTop: `1px solid ${C.line}`,
        padding: "10px 0",
        fontSize: 13,
      }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <b>{user.username}</b>{" "}
          <span style={{ color: C.sub }}>{user.full_name}</span>{" "}
          <Pill text={user.role} color={tone.color} soft={tone.soft} />{" "}
          {user.is_superuser && (
            <Pill text="superuser" color={C.green} soft={C.greenSoft} />
          )}
          {!user.is_active && (
            <Pill text="disabled" color={C.red} soft={C.redSoft} />
          )}
          <div style={{ fontSize: 11.5, color: C.sub, marginTop: 3 }}>
            {user.email || "no email"} · last in{" "}
            {user.last_login_at ? user.last_login_at.slice(0, 10) : "never"} ·{" "}
            {user.campaigns.length
              ? user.campaigns.map((c) => `${c[1]} (${c[2]})`).join(", ")
              : "on no campaign"}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Danger
            label="Reset password"
            question={`Reset ${user.username}'s password? They are signed out.`}
            busy={resetting}
            // Resetting your own password ends your own session before the new
            // one reaches the screen, so the console refuses; the server does
            // too. Use the CLI: campaign-crm reset-password.
            disabled={isMe || resetting}
            onConfirm={() => onReset(user.id)}
          />
          {user.is_active ? (
            <Danger
              label="Disable"
              question={`Disable ${user.username}? They are signed out.`}
              busy={active.isPending}
              disabled={isMe || active.isPending}
              onConfirm={() => active.mutate({ id: user.id, active: false })}
            />
          ) : (
            <Btn
              disabled={isMe || active.isPending}
              onClick={() => active.mutate({ id: user.id, active: true })}
            >
              Enable
            </Btn>
          )}
        </div>
      </div>
      {error && (
        <div style={{ color: C.red, fontSize: 12.5, marginTop: 6 }}>
          {error}
        </div>
      )}
    </div>
  );
}

const WRAP = {
  minHeight: "100vh",
  background: C.paper,
  color: C.ink,
  fontFamily: "Inter, system-ui, sans-serif",
};

// The header carries the only way out of the console, so every state renders
// inside it: a signed-out operator can always sign out and back in.
function Shell({ me, logout, children }) {
  return (
    <div style={WRAP}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;600;700&family=Inter:wght@400;500;600&display=swap');`}</style>
      <div
        className="flex flex-wrap items-center justify-between gap-3"
        style={{ padding: "14px 22px", background: C.ink, color: "#fff" }}
      >
        <div>
          <span style={{ ...DISPLAY, fontSize: 20, fontWeight: 700 }}>
            MZIGO<span style={{ color: "#7FD1A3" }}>·</span>ADMIN
          </span>
          <span style={{ fontSize: 12.5, color: "#AEB6B0", marginLeft: 10 }}>
            every campaign on this deployment
          </span>
        </div>
        <div className="flex items-center gap-3" style={{ fontSize: 12.5 }}>
          <span style={{ color: "#AEB6B0" }}>{me?.username}</span>
          <button
            onClick={logout}
            style={{
              padding: "6px 12px",
              borderRadius: 8,
              border: "1px solid #3A423C",
              background: "transparent",
              color: "#fff",
              cursor: "pointer",
              fontSize: 12.5,
            }}
          >
            Sign out
          </button>
        </div>
      </div>
      <div
        style={{ maxWidth: 1100, margin: "0 auto", padding: "22px 16px 60px" }}
      >
        {children}
      </div>
    </div>
  );
}

export default function Admin() {
  const me = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  const overview = useAdminOverview();
  const [roleFilter, setRoleFilter] = useState("");
  const users = useAdminUsers(roleFilter);
  const [tab, setTab] = useState("campaigns");
  const [handouts, setHandouts] = useState([]);
  // Owned here, not in the row: a row unmounts on every refetch and would take
  // the one-time password with it. One mutation serves every row, and it only
  // remembers its latest call, so what each row shows is kept by id.
  const [failed, setFailed] = useState({});
  const [running, setRunning] = useState(() => new Set());
  const forget = (id) => setFailed(({ [id]: _gone, ...rest }) => rest);
  const reset = useResetPassword({
    onPassword: (r) =>
      setHandouts((h) => [...h.filter((p) => p.username !== r.username), r]),
    onFailed: (error, { id }) =>
      setFailed((f) => ({ ...f, [id]: error.message })),
    onDone: ({ id }) =>
      setRunning((ids) => {
        const left = new Set(ids);
        left.delete(id);
        return left;
      }),
  });
  const handOut = (r) =>
    setHandouts((h) => [...h.filter((p) => p.username !== r.username), r]);
  const create = useCreateLogin({ onPassword: handOut });
  const startReset = (id) => {
    forget(id);
    setRunning((ids) => new Set(ids).add(id));
    reset.mutate({ id });
  };

  if (overview.isLoading)
    return (
      <Shell me={me} logout={logout}>
        <span style={{ color: C.sub }}>Loading the console…</span>
      </Shell>
    );
  if (overview.error)
    return (
      <Shell me={me} logout={logout}>
        <Card>
          <div style={{ color: C.red, fontSize: 13.5 }}>
            {overview.error.message}
          </div>
          <div style={{ marginTop: 12 }}>
            <Btn onClick={() => overview.refetch()}>Try again</Btn>
          </div>
        </Card>
      </Shell>
    );

  const { totals, campaigns } = overview.data;
  const everyone = users.data || [];
  const unstaffed = campaigns.filter((c) => c.members.length === 0).length;

  return (
    <Shell me={me} logout={logout}>
      <>
        <Card pad={20}>
          <div className="flex flex-wrap gap-x-10 gap-y-4">
            <Stat label="Campaigns" value={totals.campaigns} />
            <Stat label="Logins" value={totals.users} />
            <Stat label="Places held" value={totals.members} />
            <Stat label="Targets" value={totals.targets} />
            <Stat label="Mobilizers" value={totals.mobilizers} />
            <Stat label="Events" value={totals.events} />
            <Stat label="Supporters" value={totals.supporters} />
          </div>
          {unstaffed > 0 && (
            <div style={{ color: C.red, fontSize: 12.5, marginTop: 14 }}>
              {unstaffed} campaign{unstaffed === 1 ? "" : "s"} with nobody on{" "}
              {unstaffed === 1 ? "it" : "them"}: nobody can see{" "}
              {unstaffed === 1 ? "it" : "them"} until somebody is put on.
            </div>
          )}
        </Card>

        <Handout shown={handouts} />

        <div
          className="flex gap-1"
          style={{ margin: "20px 0 14px", fontSize: 13 }}
        >
          {[
            ["campaigns", `Campaigns (${campaigns.length})`],
            ["users", `Logins (${everyone.length})`],
          ].map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              style={{
                padding: "7px 14px",
                borderRadius: 999,
                cursor: "pointer",
                border: `1px solid ${tab === key ? C.ink : C.line}`,
                background: tab === key ? C.ink : "transparent",
                color: tab === key ? "#fff" : C.sub,
                fontWeight: 600,
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === "campaigns" &&
          (campaigns.length === 0 ? (
            <Card>
              <span style={{ color: C.sub, fontSize: 13.5 }}>
                No campaigns yet.
              </span>
            </Card>
          ) : (
            campaigns.map((c) => (
              <CampaignCard key={c.id} campaign={c} users={everyone} />
            ))
          ))}

        {tab === "users" && (
          <Card>
            <div
              className="flex flex-wrap items-center gap-1"
              style={{ fontSize: 12 }}
            >
              {[
                ["", "Everyone"],
                ["manager", "Managers"],
                ["candidate", "Aspirants"],
                ["mobilizer", "Mobilizers"],
              ].map(([key, label]) => (
                <button
                  key={key || "all"}
                  onClick={() => {
                    setRoleFilter(key);
                    setFailed({});
                  }}
                  style={{
                    padding: "5px 11px",
                    borderRadius: 999,
                    cursor: "pointer",
                    border: `1px solid ${roleFilter === key ? C.ink : C.line}`,
                    background: roleFilter === key ? C.ink : "transparent",
                    color: roleFilter === key ? "#fff" : C.sub,
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
            <div style={{ marginTop: 14 }}>
              <NewLogin campaigns={campaigns} create={create} />
            </div>
            <div style={{ marginTop: 8 }}>
              {users.isPending ? (
                <div style={{ color: C.sub, fontSize: 13, paddingTop: 10 }}>
                  Loading the logins…
                </div>
              ) : everyone.length === 0 ? (
                <div style={{ color: C.sub, fontSize: 13, paddingTop: 10 }}>
                  Nobody matches that.
                </div>
              ) : (
                everyone.map((u) => (
                  <UserRow
                    key={u.id}
                    user={u}
                    me={me?.id}
                    onReset={startReset}
                    resetting={running.has(u.id)}
                    resetError={failed[u.id]}
                  />
                ))
              )}
            </div>
          </Card>
        )}
      </>
    </Shell>
  );
}
