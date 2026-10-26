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
import { formatNumber as fmt } from "../lib/format";
import {
  Button,
  Field as SharedField,
  LoadingState,
  Panel,
} from "./ui";
import Onboarding from "./Onboarding";

const Card = (props) => (
  <Panel
    {...props}
    className={`admin-card ${props.pad === 20 ? "admin-card-padded" : ""} ${props.className || ""}`.trim()}
  />
);

const Btn = ({ children, onClick, disabled, tone }) => (
  <Button
    onClick={onClick}
    disabled={disabled}
    tone={tone}
    className="admin-button"
  >
    {children}
  </Button>
);

const Pill = ({ text }) => (
  <span className={`admin-pill admin-pill-${text}`}>
    {text}
  </span>
);

// Nothing here can be undone, and the rows are close together, so the
// destructive actions ask first and name who they are about.
function Danger({ label, question, onConfirm, disabled, busy }) {
  const [asking, setAsking] = useState(false);
  if (!asking)
    return (
      <Btn disabled={disabled} onClick={() => setAsking(true)}>
        {busy ? "Working…" : label}
      </Btn>
    );
  return (
    <span className="flex flex-wrap items-center gap-2 admin-confirmation">
      <span className="admin-red">{question}</span>
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

function Stat({ label, value }) {
  return (
    <div>
      <div className="admin-display admin-stat-value">
        {fmt(value)}
      </div>
      <div className="admin-stat-label">{label}</div>
    </div>
  );
}

// Passwords come back once. Nothing re-fetches them, so they live here until
// the console is closed.
function Handout({ shown }) {
  if (!shown.length) return null;
  return (
    <Card className="admin-card-handout">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="admin-display admin-handout-heading">
          Write these down now
        </div>
        <span className="admin-handout-note">
          shown once, never fetchable again
        </span>
      </div>
      <table className="admin-handout-table">
        <tbody>
          {shown.map((p, i) => (
            <tr
              key={p.username}
              className={i ? "admin-handout-row" : undefined}
            >
              <td className="admin-handout-cell admin-handout-username">
                {p.username}
              </td>
              <td className="admin-handout-cell admin-handout-password">
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

  // A login belongs to one campaign, so only a login on none is offered. A
  // superuser reads every campaign through this console, and a disabled login
  // cannot sign in, so neither is offered either.
  const available = users.filter(
    (u) => !u.campaign && !u.is_superuser && u.is_active,
  );
  const error = remove.error || add.error || rename.error || drop.error;

  return (
    <Card className="admin-card-campaign">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          {renaming ? (
            <div className="flex flex-wrap items-center gap-2">
              <input
                className="admin-field admin-field-campaign"
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
              <div className="admin-display admin-campaign-title">
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
                question={`Delete ${campaign.title} with its ${fmt(campaign.targets)} targets, ${fmt(campaign.mobilizers)} mobilizers, ${fmt(campaign.events)} events and ${fmt(campaign.supporters)} supporters, and the login of everyone on it except a superuser? This cannot be undone.`}
                busy={drop.isPending}
                disabled={drop.isPending}
                onConfirm={() => drop.mutate({ campaign: campaign.id })}
              />
            </div>
          )}
          <div className="admin-campaign-meta admin-subtle">
            {campaign.office_level} · for {campaign.candidate || "no candidate"}{" "}
            · {campaign.election_date || "no election date"}
          </div>
        </div>
        <div className="flex flex-wrap gap-4 admin-campaign-counts">
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

      <div className="admin-campaign-members">
        {campaign.members.length === 0 && (
          <div className="admin-red admin-campaign-meta">
            Nobody is on this campaign, so nobody can see it. Add someone below.
          </div>
        )}
        {campaign.members.map((m) => {
          return (
            <div
              key={m.user_id}
              className="flex flex-wrap items-center justify-between gap-2 admin-campaign-member"
            >
              <span>
                <b>{m.username}</b>{" "}
                <span className="admin-subtle">{m.full_name}</span>{" "}
                <Pill text={m.role} />
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
        <div className="admin-error">
          {error.message}
        </div>
      )}

      <div className="admin-add-member">
        {adding ? (
          <div className="flex flex-wrap items-center gap-2">
            <select
              className="admin-field"
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
            <span className="admin-subtle admin-confirmation">
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
  centre: "",
};

// The server takes `^[A-Za-z0-9._-]+$`, 3 to 150 characters.
const USERNAME = /^[A-Za-z0-9._-]+$/;

const ROLES = [
  ["manager", "Campaign manager"],
  ["mobilizer", "Mobilizer"],
];

const Field = ({ label, children }) => (
  <SharedField label={label} className="admin-field-label">
    {children}
  </SharedField>
);

function NewLogin({ campaigns, create }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(BLANK);
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  const chosen = campaigns.find((c) => c.id === form.campaign);
  const isMobilizer = form.role === "mobilizer";
  // An MCA campaign is worked by centre, so its mobilizer is placed on one with a target.
  const centres = chosen?.centres || [];
  const byCentre = centres.length > 0;
  const name = form.username.trim();
  const ready =
    name.length >= 3 &&
    name.length <= 150 &&
    USERNAME.test(name) &&
    (!isMobilizer || (form.campaign && form.ward));

  if (!open)
    return (
      <div className="admin-section-action">
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
        registration_centre: isMobilizer && byCentre ? form.centre || null : null,
      },
      {
        onSuccess: () => {
          setForm(BLANK);
          setOpen(false);
        },
      },
    );

  return (
    <Card className="admin-card-new-login">
      <div className="admin-display admin-form-heading">
        A new login
      </div>

      <div className="flex flex-wrap gap-2">
        <Field label="Username">
          <input
            className="admin-field admin-field-wide"
            value={form.username}
            onChange={(e) => set({ username: e.target.value })}
            placeholder="jane.wanjiku"
          />
        </Field>
        <Field label="They are a">
          <select
            className="admin-field admin-field-wide"
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

      <div className="admin-form-spacer" />
      <div className="flex flex-wrap gap-2">
        <Field label="First name">
          <input
            className="admin-field admin-field-wide"
            value={form.first_name}
            onChange={(e) => set({ first_name: e.target.value })}
          />
        </Field>
        <Field label="Last name">
          <input
            className="admin-field admin-field-wide"
            value={form.last_name}
            onChange={(e) => set({ last_name: e.target.value })}
          />
        </Field>
      </div>

      <div className="admin-form-spacer" />
      <div className="flex flex-wrap gap-2">
        <Field label="Email">
          <input
            type="email"
            className="admin-field admin-field-wide"
            value={form.email}
            onChange={(e) => set({ email: e.target.value })}
          />
        </Field>
        <Field label="Phone">
          <input
            className="admin-field admin-field-wide"
            value={form.phone}
            onChange={(e) => set({ phone: e.target.value })}
            placeholder="0712 345678"
          />
        </Field>
      </div>

      <>
        <div className="admin-form-spacer" />
        <div className="flex flex-wrap gap-2">
          <Field label={isMobilizer ? "Campaign" : "Campaign (optional)"}>
            <select
              className="admin-field admin-field-wide"
              value={form.campaign}
              onChange={(e) => set({ campaign: e.target.value, ward: "", centre: "" })}
            >
              <option value="">On no campaign yet…</option>
              {campaigns.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
          </Field>
          {isMobilizer && byCentre && (
            <Field label="Centre">
              <select
                className="admin-field admin-field-wide"
                value={form.centre}
                onChange={(e) => {
                  const centre = centres.find((c) => c.id === e.target.value);
                  set({ centre: e.target.value, ward: centre?.ward || "" });
                }}
              >
                <option value="">Choose a centre…</option>
                {centres.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </Field>
          )}
          {isMobilizer && !byCentre && (
            <Field label="Ward">
              <select
                className="admin-field admin-field-wide"
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

      <div className="admin-form-help">
        {isMobilizer
          ? byCentre
            ? "In an MCA race a mobilizer works one registration centre."
            : "A mobilizer works one ward, and sees only that ward."
          : "Leave the campaign blank to create the login now and place it later."}{" "}
        An aspirant gets their login with their campaign, from New campaign.{" "}
        Their password is shown once, above. Write it down.
      </div>

      {create.error && (
        <div className="admin-error">
          {create.error.message}
        </div>
      )}

      <div className="flex flex-wrap gap-2 admin-form-actions">
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
  const isMe = user.id === me;
  const error = resetError || active.error?.message;

  return (
    <div
      data-testid={`login-${user.username}`}
      className="admin-user-row"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <b>{user.username}</b>{" "}
          <span className="admin-subtle">{user.full_name}</span>{" "}
          <Pill text={user.role} />{" "}
          {user.is_superuser && (
            <Pill text="superuser" />
          )}
          {!user.is_active && (
            <Pill text="disabled" />
          )}
          <div className="admin-user-meta">
            {user.email || "no email"} · last in{" "}
            {user.last_login_at ? user.last_login_at.slice(0, 10) : "never"} ·{" "}
            {user.campaign || "on no campaign"}
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
        <div className="admin-user-error">
          {error}
        </div>
      )}
    </div>
  );
}

// The header carries the only way out of the console, so every state renders
// inside it: a signed-out operator can always sign out and back in.
function Shell({ me, logout, children }) {
  return (
    <div className="admin-shell">
      <div className="flex flex-wrap items-center justify-between gap-3 admin-header">
        <div>
          <span className="admin-display admin-brand">
            MZIGO<span className="admin-brand-mark">·</span>ADMIN
          </span>
          <span className="admin-header-description">
            every campaign on this deployment
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="admin-header-user">{me?.username}</span>
          <button className="admin-header-signout" onClick={logout}>
            Sign out
          </button>
        </div>
      </div>
      <div className="admin-content">{children}</div>
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
  const [creating, setCreating] = useState(false);
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

  // Before the overview's own states, so a failed refetch cannot take the
  // wizard, and the passwords on its last screen, with it.
  if (creating)
    return (
      <Onboarding
        onLogin={handOut}
        onCancel={() => setCreating(false)}
        onDone={() => {
          setTab("campaigns");
          setCreating(false);
        }}
      />
    );

  if (overview.isLoading)
    return (
      <Shell me={me} logout={logout}>
        <span className="admin-subtle">Loading the console…</span>
      </Shell>
    );
  if (overview.error)
    return (
      <Shell me={me} logout={logout}>
        <Card>
          <div className="admin-red admin-overview-error">
            {overview.error.message}
          </div>
          <div className="admin-overview-action">
            <Btn onClick={() => overview.refetch()}>Try again</Btn>
          </div>
        </Card>
        <Handout shown={handouts} />
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
            <div className="admin-red admin-unstaffed">
              {unstaffed} campaign{unstaffed === 1 ? "" : "s"} with nobody on{" "}
              {unstaffed === 1 ? "it" : "them"}: nobody can see{" "}
              {unstaffed === 1 ? "it" : "them"} until somebody is put on.
            </div>
          )}
        </Card>

        <Handout shown={handouts} />

        <div className="flex gap-1 admin-tab-bar">
          {[
            ["campaigns", `Campaigns (${campaigns.length})`],
            ["users", `Logins (${everyone.length})`],
          ].map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`admin-tab ${tab === key ? "admin-tab-active" : ""}`}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === "campaigns" && (
          <div className="admin-section-action">
            <Btn onClick={() => setCreating(true)}>New campaign</Btn>
          </div>
        )}

        {tab === "campaigns" &&
          (campaigns.length === 0 ? (
            <Card>
              <span className="admin-subtle admin-empty-message">
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
              className="flex flex-wrap items-center gap-1 admin-user-filters"
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
                  className={`admin-filter ${roleFilter === key ? "admin-filter-active" : ""}`}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="admin-user-section">
              <NewLogin campaigns={campaigns} create={create} />
            </div>
            <div className="admin-user-list">
              {users.isPending ? (
                <LoadingState
                  className="admin-loading"
                  message="Loading the logins…"
                />
              ) : everyone.length === 0 ? (
                <div className="admin-empty">
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
