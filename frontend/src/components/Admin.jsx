// src/components/Admin.jsx
// The console for whoever runs the deployment: every campaign on it, every
// login, and the few repairs that cannot be done from inside a campaign.
// Shown only to a superuser; every route it calls checks the flag again.
import React, { useState } from "react";
import { isEmail } from "../lib/email";
import { isUsername } from "../lib/username";
import { useNavigate } from "react-router-dom";
import { PARTY_ROLES, PARTY_ROLE_LABEL } from "../pages/party/helpers";
import {
  useAdminOverview,
  rowsOf,
  useAdminUserPages,
  useAdminUsers,
  useAddMember,
  useCreateLogin,
  useDeleteCampaign,
  useGrantPartyRole,
  useLinkPartyMember,
  useOpenPartyWorkspace,
  useParty,
  useSite,
  usePartyMembers,
  usePartyWorkspace,
  useRevokePartyRole,
  useSaveSettings,
  useRenameCampaign,
  useRemoveMember,
  useResetPassword,
  useSetActive,
  useSetEmail,
} from "../api/hooks";
import { useInstall } from "../app/site";
import { useCopy } from "../copy";
import { useAuth } from "../store/auth";
import { formatNumber as fmt, plural } from "../lib/format";
import { SlottedHeader } from "@/components/layout/AppPage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorText } from "@/components/ui/error-text";
import { Field, Input, NativeSelect, Textarea } from "@/components/ui/input";
import { LoadingText } from "@/components/ui/loading-text";
import { FilterPills } from "@/components/ui/tabs";
import { PartyShell } from "../pages/party/Portal";
import AuditTrail from "./console/AuditTrail";
import ExportPanel from "./console/ExportPanel";
import Health from "./console/Health";
import ReferenceData from "./console/ReferenceData";
import { LoadMore } from "@/components/ui/load-more";

const Btn = ({ children, onClick, disabled, variant = "quiet" }) => (
  <Button shape="rounded" size="sm" variant={variant} onClick={onClick} disabled={disabled}>
    {children}
  </Button>
);

const PILL_TONE = { candidate: "tint", superuser: "tint", manager: "stone", mobilizer: "warn", disabled: "bad" };

const Pill = ({ text }) => <Badge tone={PILL_TONE[text] || "stone"}>{text}</Badge>;

// An inline control: full width on a phone, sharing the row from sm up.
const INLINE = "w-full sm:w-auto sm:min-w-56 sm:flex-1";

const Help = ({ children }) => <p className="text-small leading-relaxed text-muted-foreground">{children}</p>;

const Heading = ({ children }) => <h2 className="text-card-title font-bold">{children}</h2>;

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
    <span className="flex flex-wrap items-center gap-2">
      <span className="text-ui text-destructive">{question}</span>
      <Btn
        variant="danger"
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

// Which sign-in links went out this visit, kept until the console is closed.
function Handout({ shown }) {
  if (!shown.length) return null;
  return (
    <Card variant="outline" className="gap-2 border-warn bg-warn/40">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-body font-bold">Sign-in links</h2>
        <span className="text-small text-warn-foreground">each person chooses their own password</span>
      </div>
      <ul className="flex flex-col divide-y divide-warn text-ui">
        {shown.map((p) => (
          <li key={p.username} className="flex flex-wrap justify-between gap-x-4 gap-y-1 py-2">
            <span className="font-semibold break-all">{p.username}</span>
            <span>{(p.sent ?? p.invite) === "email" ? "Link emailed" : "No email: nothing sent"}</span>
          </li>
        ))}
      </ul>
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

  // A login belongs to one campaign, so only a login on none is offered, and
  // staff with no campaign role cannot take a place. A
  // superuser reads every campaign through this console, and a disabled login
  // cannot sign in, so neither is offered either.
  const available = users.filter(
    (u) => u.role && !u.campaign && !u.is_superuser && u.is_active,
  );
  const error = remove.error || add.error || rename.error || drop.error;

  return (
    <Card variant="outline" className="min-w-0">
      <div className="flex flex-col gap-2">
        <div className="flex min-w-0 flex-col gap-1">
          {renaming ? (
            <div className="flex flex-wrap items-center gap-2">
              <Input
                className={INLINE}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                aria-label="Campaign name"
              />
              <Btn
                variant="primary"
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
              <h2 className="text-card-title font-bold break-words">
                {campaign.title}
              </h2>
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
          <div className="text-ui text-muted-foreground">
            {campaign.office_level} · for {campaign.candidate || "no candidate"}{" "}
            · {campaign.election_date || "no election date"}
          </div>
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-ui [&_b]:tabular-nums">
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

      <div className="flex flex-col border-t border-line pt-2">
        {campaign.members.length === 0 && (
          <div className="py-1.5 text-ui text-destructive">
            Nobody is on this campaign, so nobody can see it. Add someone below.
          </div>
        )}
        {campaign.members.map((m) => {
          return (
            <div
              key={m.user_id}
              className="flex flex-wrap items-center justify-between gap-2 py-1.5 text-ui"
            >
              <span className="min-w-0 break-words">
                <b>{m.username}</b>{" "}
                <span className="text-muted-foreground">{m.full_name}</span>{" "}
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

      <ErrorText error={error} className="text-ui" />

      <div>
        {adding ? (
          <div className="flex flex-wrap items-center gap-2">
            <NativeSelect
              className={INLINE}
              value={pick}
              onChange={(e) => setPick(e.target.value)}
            >
              <option value="">Choose a login…</option>
              {available.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.username} ({u.role})
                </option>
              ))}
            </NativeSelect>
            <span className="text-ui text-muted-foreground">
              as {available.find((u) => u.id === pick)?.role || "themselves"}
            </span>
            <Btn
              variant="primary"
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

const ROLES = [
  ["manager", "Campaign manager"],
  ["mobilizer", "Mobilizer"],
  ["staff", "Party staff (no campaign)"],
];


function NewLogin({ campaigns, create }) {
  const { aspirant } = useInstall();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(BLANK);
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  const chosen = campaigns.find((c) => c.id === form.campaign);
  const isMobilizer = form.role === "mobilizer";
  const isStaff = form.role === "staff";
  // An MCA campaign is worked by centre, so its mobilizer is placed on one with a target.
  const centres = chosen?.centres || [];
  const byCentre = centres.length > 0;
  const name = form.username.trim();
  const ready =
    isUsername(name) &&
    isEmail(form.email) &&
    (!isMobilizer || (form.campaign && form.ward));

  if (!open)
    return (
      <div>
        <Btn onClick={() => setOpen(true)}>Add a login</Btn>
      </div>
    );

  const submit = () =>
    create.mutate(
      {
        username: name.toLowerCase(),
        role: isStaff ? null : form.role,
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        email: form.email.trim(),
        phone: form.phone.trim(),
        campaign: isStaff ? null : form.campaign || null,
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
    <Card variant="tinted" className="gap-3">
      <Heading>A new login</Heading>

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Username">
          <Input
            value={form.username}
            onChange={(e) => set({ username: e.target.value })}
            placeholder="jane.wanjiku"
          />
        </Field>
        <Field label="They are a">
          <NativeSelect
            value={form.role}
            onChange={(e) =>
              set({ role: e.target.value, campaign: "", ward: "" })
            }
          >
            {ROLES.filter(([value]) => !aspirant || value !== "staff").map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </NativeSelect>
        </Field>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="First name">
          <Input
            value={form.first_name}
            onChange={(e) => set({ first_name: e.target.value })}
          />
        </Field>
        <Field label="Last name">
          <Input
            value={form.last_name}
            onChange={(e) => set({ last_name: e.target.value })}
          />
        </Field>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Email">
          <Input
            type="email"
            value={form.email}
            onChange={(e) => set({ email: e.target.value })}
          />
        </Field>
        <Field label="Phone">
          <Input
            value={form.phone}
            onChange={(e) => set({ phone: e.target.value })}
            placeholder="0712 345678"
          />
        </Field>
      </div>

      {!isStaff && (
      <>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={isMobilizer ? "Campaign" : "Campaign (optional)"}>
            <NativeSelect
              value={form.campaign}
              onChange={(e) => set({ campaign: e.target.value, ward: "", centre: "" })}
            >
              <option value="">On no campaign yet…</option>
              {campaigns.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </NativeSelect>
          </Field>
          {isMobilizer && byCentre && (
            <Field label="Centre">
              <NativeSelect
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
              </NativeSelect>
            </Field>
          )}
          {isMobilizer && !byCentre && (
            <Field label="Ward">
              <NativeSelect
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
              </NativeSelect>
            </Field>
          )}
        </div>
      </>
      )}

      <Help>
        {isStaff
          ? "Party staff have no campaign. Give them a party office from their row once the login exists."
          : isMobilizer
          ? byCentre
            ? "In an MCA race a mobilizer works one registration centre."
            : "A mobilizer works one ward, and sees only that ward."
          : "Leave the campaign blank to create the login now and place it later."}{" "}
        {aspirant
          ? "The aspirant's login was made at setup."
          : "An aspirant gets their login with their workspace, made from their approved record in Aspirants."}{" "}
        They are emailed a link to choose their password.
      </Help>

      <ErrorText error={create.error} className="text-ui" />

      <div className="flex flex-wrap gap-2">
        <Btn variant="primary" disabled={!ready || create.isPending} onClick={submit}>
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

const NO_MANAGER = { username: "", first_name: "", last_name: "", email: "", phone: "" };
const MANAGER_FIELDS = [
  ["username", "Username", "text"],
  ["first_name", "First name", "text"],
  ["last_name", "Last name", "text"],
  ["email", "Email", "email"],
  ["phone", "Phone", "text"],
];

// A party copy's own workspace when setup did not open it; gone once it exists.
function OpenPartyWorkspace({ onInvite }) {
  const { party } = useInstall();
  const workspace = usePartyWorkspace(party);
  const replace = Boolean(workspace.data?.id);
  const [asking, setAsking] = useState(false);
  const [form, setForm] = useState(NO_MANAGER);
  const open = useOpenPartyWorkspace({
    replace,
    onInvite: (r) => {
      setAsking(false);
      setForm(NO_MANAGER);
      onInvite(r);
    },
  });
  if (!workspace.data) return null;
  const title = replace ? "Replace Workspace Manager" : "Open the party workspace";
  const sitting = workspace.data.managers?.join(", ");
  if (!asking)
    return (
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <Btn onClick={() => setAsking(true)}>{title}</Btn>
        {replace && sitting && <span className="text-ui text-muted-foreground">Workspace Manager: {sitting}</span>}
      </div>
    );
  const name = form.username.trim();
  const ready = isUsername(name) && isEmail(form.email);
  const submit = () =>
    open.mutate({
      manager: {
        username: name.toLowerCase(),
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        email: form.email.trim(),
        phone: form.phone.trim(),
      },
    });
  return (
    <Card variant="outline" className="gap-3">
      <Heading>{title}</Heading>
      <div className="grid gap-3 sm:grid-cols-2">
        {MANAGER_FIELDS.map(([key, label, type]) => (
          <Field key={key} label={label}>
            <Input
              type={type}
              value={form[key]}
              onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
            />
          </Field>
        ))}
      </div>
      <Help>
        {replace
          ? `${sitting || "The sitting Workspace Manager"} is turned off and signed out. This person takes over and is emailed a link to choose their password.`
          : "The party's own national workspace, with every ward as a target. This person is its first Workspace Manager and is emailed a link to choose their password. There is only one party workspace."}
      </Help>
      <ErrorText error={open.error} className="text-ui" />
      <div className="flex flex-wrap gap-2">
        <Btn variant="primary" disabled={!ready || open.isPending} onClick={submit}>
          {open.isPending ? (replace ? "Replacing…" : "Opening…") : replace ? "Replace" : "Open it"}
        </Btn>
        <Btn onClick={() => setAsking(false)}>Cancel</Btn>
      </div>
    </Card>
  );
}

// The party member a login belongs to; an office holder must be linked to an approved one.
function MemberLink({ user, onLinked }) {
  const link = useLinkPartyMember();
  const [q, setQ] = useState("");
  const found = usePartyMembers({ q: q.trim(), status: "approved", limit: 5 });
  const searching = q.trim().length >= 2;
  return (
    <div className="flex flex-col gap-1 text-small text-muted-foreground">
      {user.party_member ? (
        <span className="flex flex-wrap items-center gap-2">
          Party member: {user.party_member.full_name} ({user.party_member.status})
          {!user.party_roles?.length && (
            <Btn
              disabled={link.isPending}
              onClick={() => link.mutate({ user: user.id, member: null })}
            >
              Unlink
            </Btn>
          )}
        </span>
      ) : (
        <span className="flex flex-wrap items-center gap-2">
          <Input
            className={INLINE}
            aria-label={`Party member for ${user.username}`}
            placeholder="Link to a party member…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          {searching &&
            (found.data?.items || []).map((m) => (
              <Btn
                key={m.id}
                disabled={link.isPending}
                onClick={() =>
                  link.mutate(
                    { user: user.id, member: m.id },
                    { onSuccess: () => { setQ(""); onLinked(); } },
                  )
                }
              >
                {m.full_name}
              </Btn>
            ))}
        </span>
      )}
      <ErrorText error={link.isError && link.error} className="text-small" />
    </div>
  );
}

function UserRow({ user, me, onReset, resetting, resetError }) {
  // A member's own login has a machine-made username; people know it by its email.
  const name = user.kind === "member" ? user.email || user.full_name : user.username;
  const { aspirant } = useInstall();
  const active = useSetActive();
  const setEmail = useSetEmail();
  const [editingEmail, setEditingEmail] = useState(false);
  const [email, setEmailText] = useState("");
  const grant = useGrantPartyRole();
  const revoke = useRevokePartyRole();
  const [office, setOffice] = useState("");
  const isMe = user.id === me;
  const staff = user.kind === "staff" && !user.is_superuser;
  const memberLogin = user.kind === "member";
  const offered = PARTY_ROLES.filter(
    ([value]) => !user.party_roles?.includes(value),
  );
  const error =
    resetError ||
    active.error?.message ||
    setEmail.error?.message ||
    grant.error?.message ||
    revoke.error?.message;

  return (
    <div
      data-testid={`login-${user.username}`}
      className="flex flex-col gap-2 border-t border-line py-3 text-ui"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <b className="break-all">{name}</b>
            <span className="text-muted-foreground">{user.full_name}</span>
            {user.role && <Pill text={user.role} />}
            {user.party_roles?.map((r) => (
              <Badge key={r} tone="tint">
                {PARTY_ROLE_LABEL[r] || r}
                <button
                  type="button"
                  className="-my-3 -mr-3 inline-flex size-11 cursor-pointer items-center justify-center rounded-full disabled:opacity-50"
                  aria-label={`Revoke ${PARTY_ROLE_LABEL[r] || r}`}
                  disabled={revoke.isPending}
                  onClick={() => revoke.mutate({ user: user.id, role: r })}
                >
                  ×
                </button>
              </Badge>
            ))}
            {user.is_superuser && (
              <Pill text="superuser" />
            )}
            {!user.is_active && (
              <Pill text="disabled" />
            )}
          </div>
          {editingEmail ? (
            <div className="flex flex-wrap items-center gap-2">
              <Input
                type="email"
                className={INLINE}
                aria-label={`Email for ${name}`}
                value={email}
                onChange={(e) => setEmailText(e.target.value)}
              />
              <Btn
                variant="primary"
                disabled={!isEmail(email) || setEmail.isPending}
                onClick={() =>
                  setEmail.mutate(
                    { id: user.id, email: email.trim() },
                    { onSuccess: () => setEditingEmail(false) },
                  )
                }
              >
                {setEmail.isPending ? "Saving…" : "Save email"}
              </Btn>
              <Btn onClick={() => setEditingEmail(false)}>Cancel</Btn>
            </div>
          ) : null}
          <div className="flex flex-wrap items-center gap-x-1 text-small wrap-anywhere text-muted-foreground">
            {user.email || "no email"}{" "}
            {!editingEmail && (
              <Button
                variant="link"
                size="sm"
                className="relative h-auto px-1 text-small font-semibold underline max-sm:h-auto after:absolute after:inset-x-0 after:top-1/2 after:h-11 after:-translate-y-1/2"
                aria-label={`Change email for ${name}`}
                onClick={() => {
                  setEmail.reset();
                  setEmailText(user.email || "");
                  setEditingEmail(true);
                }}
              >
                change
              </Button>
            )}
            {/* Each dot keeps to the text before it, so a wrapped line never starts with one. */}
            {" ·"}{" "}
            <span className="whitespace-nowrap">last in {user.last_login_at ? user.last_login_at.slice(0, 10) : "never"}{" ·"}</span>{" "}
            {user.campaign || "on no campaign"}
          </div>
          {!aspirant && <div className="text-small text-muted-foreground">
            {staff
              ? offered.length > 0 && (
                  <span className="flex flex-wrap items-center gap-2">
                    <NativeSelect
                      className={INLINE}
                      aria-label={`Party office for ${name}`}
                      value={office}
                      onChange={(e) => setOffice(e.target.value)}
                    >
                      <option value="">Give a party office…</option>
                      {offered.map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </NativeSelect>
                    <Btn
                      variant="primary"
                      disabled={!office || grant.isPending}
                      onClick={() =>
                        grant.mutate(
                          { user: user.id, role: office },
                          { onSuccess: () => setOffice("") },
                        )
                      }
                    >
                      {grant.isPending ? "Granting…" : "Grant"}
                    </Btn>
                  </span>
                )
              : memberLogin
              ? "A member's own login. A party office goes on a staff login linked to this member."
              : "Party offices go only to staff logins with no campaign role."}
          </div>}
          {staff && !aspirant && <MemberLink user={user} onLinked={() => grant.reset()} />}
        </div>
        <div className="flex flex-wrap gap-2">
          <Danger
            label="Send reset link"
            question={`Email ${name} a link to choose a new password?`}
            busy={resetting}
            // Your own password: use Forgot password on the sign-in page.
            disabled={isMe || resetting}
            onConfirm={() => onReset(user.id)}
          />
          {user.is_active ? (
            <Danger
              label="Disable"
              question={`Disable ${name}? They are signed out.`}
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
      <ErrorText error={error} className="text-ui" />
    </div>
  );
}

const PARTY_TEXT = [
  ["name", "Name"],
  ["short_name", "Short name"],
  ["slogan", "Slogan"],
  ["registration_number", "Registration number"],
  ["about_headline", "About page headline"],
  ["founded_year", "Year founded"],
  ["logo_url", "Logo URL"],
  ["contact_email", "Contact email"],
  ["contact_phone", "Phone"],
  ["address", "Address"],
  ["manifesto_url", "Manifesto URL"],
  ["privacy_notice_version", "Privacy notice version"],
];

const partyForm = (party) => ({
  ...Object.fromEntries(
    [
      ...PARTY_TEXT.map(([key]) => key),
      "primary_colour",
      "secondary_colour",
      "description",
      "manifesto_text",
      "aspirant_steps",
      "privacy_notice",
      "payment_instructions",
      "mpesa_paybill",
      "mpesa_account",
      "mpesa_till",
    ].map((key) => [key, party[key] ?? ""]),
  ),
  links: Object.entries(party.social_links || {}),
});

// Party-only fields, which an aspirant installation's settings leave out.
const PARTY_ONLY = new Set(["registration_number", "founded_year", "aspirant_steps"]);

function PartyForm({ party, isParty }) {
  const save = useSaveSettings({ party: isParty });
  const [form, setForm] = useState(() => partyForm(party));
  const [saved, setSaved] = useState(false);
  const set = (patch) => {
    setSaved(false);
    setForm((f) => ({ ...f, ...patch }));
  };
  const setLink = (i, at, value) =>
    set({
      links: form.links.map((pair, j) =>
        j === i ? pair.map((v, k) => (k === at ? value : v)) : pair,
      ),
    });

  const submit = () => {
    const { links, ...all } = form;
    const rest = isParty ? all : Object.fromEntries(Object.entries(all).filter(([key]) => !PARTY_ONLY.has(key)));
    save.mutate(
      {
        ...rest,
        social_links: Object.fromEntries(
          links
            .map(([name, url]) => [name.trim(), url.trim()])
            .filter(([name]) => name),
        ),
      },
      { onSuccess: () => setSaved(true) },
    );
  };

  return (
    <Card variant="outline">
      <Heading>{isParty ? "Party settings" : "Site settings"}</Heading>
      <div className="grid gap-3 sm:grid-cols-2">
        {PARTY_TEXT.filter(([key]) => isParty || !PARTY_ONLY.has(key)).map(([key, label]) => (
          <Field key={key} label={label}>
            <Input
              value={form[key]}
              onChange={(e) => set({ [key]: e.target.value })}
            />
          </Field>
        ))}
        <Field label="Primary colour">
          <Input
            value={form.primary_colour}
            onChange={(e) => set({ primary_colour: e.target.value })}
            placeholder="#1f2937"
          />
        </Field>
        <Field label="Secondary colour">
          <Input
            value={form.secondary_colour}
            onChange={(e) => set({ secondary_colour: e.target.value })}
            placeholder="#f59e0b"
          />
        </Field>
      </div>
      <Field label="Description">
        <Textarea
          value={form.description}
          onChange={(e) => set({ description: e.target.value })}
        />
      </Field>
      <Field label="Manifesto text">
        <Textarea
          value={form.manifesto_text}
          onChange={(e) => set({ manifesto_text: e.target.value })}
        />
      </Field>
      {isParty ? (
        <Field label="Steps to become an aspirant (one per line)">
          <Textarea
            value={form.aspirant_steps}
            onChange={(e) => set({ aspirant_steps: e.target.value })}
          />
        </Field>
      ) : null}
      <Field label="How to give (shown on the Contribute page)">
        <Textarea
          value={form.payment_instructions}
          onChange={(e) => set({ payment_instructions: e.target.value })}
          placeholder="Bank details, or how to give in person"
        />
      </Field>
      <div className="flex flex-col gap-2">
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            ["mpesa_paybill", "M-Pesa Paybill", "e.g. 123456"],
            ["mpesa_account", "Paybill account", "e.g. DONATE"],
            ["mpesa_till", "or M-Pesa Till", "e.g. 654321"],
          ].map(([key, label, hint]) => (
            <Field key={key} label={label}>
              <Input
                value={form[key]}
                placeholder={hint}
                onChange={(e) => set({ [key]: e.target.value.trim() })}
              />
            </Field>
          ))}
        </div>
        <Help>The Contribute page and the nomination fee offer these to pay by code. Give a Paybill or a Till, not both.</Help>
      </div>
      <Field label="Privacy notice">
        <Textarea
          value={form.privacy_notice}
          onChange={(e) => set({ privacy_notice: e.target.value })}
        />
      </Field>
      <div className="flex flex-col gap-2">
        <h3 className="text-body font-bold">Social links</h3>
        {form.links.map(([name, url], i) => (
          <div key={i} className="flex flex-wrap items-center gap-2">
            <Input
              className="w-full sm:w-44"
              aria-label={`Social link ${i + 1} name`}
              value={name}
              onChange={(e) => setLink(i, 0, e.target.value)}
              placeholder="facebook"
            />
            <Input
              className={INLINE}
              aria-label={`Social link ${i + 1} address`}
              value={url}
              onChange={(e) => setLink(i, 1, e.target.value)}
              placeholder="https://"
            />
            <Btn
              onClick={() =>
                set({ links: form.links.filter((_, j) => j !== i) })
              }
            >
              Remove
            </Btn>
          </div>
        ))}
        <div>
          <Btn onClick={() => set({ links: [...form.links, ["", ""]] })}>
            Add a link
          </Btn>
        </div>
      </div>

      <ErrorText error={save.error} className="text-ui" />
      {saved && <p role="status" className="text-ui font-semibold text-primary">Saved.</p>}

      <div className="flex flex-wrap gap-2">
        <Btn variant="primary" disabled={save.isPending} onClick={submit}>
          {save.isPending ? "Saving…" : isParty ? "Save the party settings" : "Save the site settings"}
        </Btn>
      </div>
    </Card>
  );
}

function Failed({ error, onRetry }) {
  return (
    <Card variant="outline" className="gap-3">
      <ErrorText error={error} />
      <div>
        <Btn onClick={onRetry}>Try again</Btn>
      </div>
    </Card>
  );
}

function PartySettings() {
  const site = useSite();
  const isParty = site.data?.organisation_type === "party";
  const party = useParty(isParty);
  if (site.isPending || (isParty && party.isPending))
    return <LoadingText>{site.data?.organisation_type === "aspirant" ? "Loading the site settings…" : "Loading the party settings…"}</LoadingText>;
  const failed = [site, ...(isParty ? [party] : [])].find((q) => q.error);
  if (failed) return <Failed error={failed.error} onRetry={() => failed.refetch()} />;
  return (
    <PartyForm
      key={`${site.data.updated_at} ${party.data?.updated_at}`}
      party={{ ...site.data, ...party.data }}
      isParty={isParty}
    />
  );
}

/** A wrapping row of toggle buttons with one pressed. */
function Choices({ label, options, value, onChange }) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-2">
      {options.map(([key, text]) => (
        <Button
          key={key || "all"}
          shape="rounded"
          size="sm"
          variant={value === key ? "primary" : "quiet"}
          aria-pressed={value === key}
          onClick={() => onChange(key)}
        >
          {text}
        </Button>
      ))}
    </div>
  );
}

// The shell's menu carries the only way out of the console, so every state renders
// inside it: a signed-out operator can always sign out and back in.
function Shell({ children }) {
  return (
    <PartyShell crumb="Console" page={{ kit: true }}>
      <SlottedHeader title="Console" />
      {children}
    </PartyShell>
  );
}

export default function Admin() {
  const me = useAuth((s) => s.user);
  const { aspirant } = useInstall();
  const copy = useCopy();
  const overview = useAdminOverview();
  const [roleFilter, setRoleFilter] = useState("");
  // Every login, for the campaign pickers and the tab count; the Logins tab lists them a page at a time.
  const users = useAdminUsers();
  const loginPages = useAdminUserPages(roleFilter);
  const [tab, setTab] = useState("campaigns");
  const navigate = useNavigate();
  const [handouts, setHandouts] = useState([]);
  // Owned here, not in the row: a row unmounts on every refetch. One mutation
  // serves every row, and it only remembers its latest call, so what each row
  // shows is kept by id.
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
      <Shell>
        <LoadingText>Loading the console…</LoadingText>
      </Shell>
    );
  if (overview.error)
    return (
      <Shell>
        <Failed error={overview.error} onRetry={() => overview.refetch()} />
        <Handout shown={handouts} />
      </Shell>
    );

  const { totals, campaigns } = overview.data;
  const everyone = users.data || [];
  const listed = rowsOf(loginPages.data);
  const unstaffed = campaigns.filter((c) => c.members.length === 0).length;

  return (
    <Shell>
      <div className="flex flex-col gap-3">
        <Card variant="outline" role="group" aria-label="Totals" className="flex-row flex-wrap gap-x-8 gap-y-4 px-6 py-5">
          {[
            ["Campaigns", totals.campaigns],
            ["Logins", totals.users],
            ["Places held", totals.members],
            ["Targets", totals.targets],
            ["Mobilizers", totals.mobilizers],
            ["Events", totals.events],
            ["Supporters", totals.supporters],
          ].map(([label, value]) => (
            <div key={label} className="flex flex-col">
              <span className="font-display text-h2-app leading-tight font-extrabold tabular-nums">{fmt(value)}</span>
              <span className="text-small text-muted-foreground">{label}</span>
            </div>
          ))}
        </Card>
        {unstaffed > 0 && (
          <p className="text-ui font-semibold text-destructive">
            {plural(unstaffed, "campaign")} with nobody on{" "}
            {unstaffed === 1 ? "it" : "them"}: nobody can see{" "}
            {unstaffed === 1 ? "it" : "them"} until somebody is put on.
          </p>
        )}
      </div>

      <Handout shown={handouts} />

      <div className="flex flex-col gap-4">
        <Choices
          label="Console sections"
          value={tab}
          onChange={setTab}
          options={[
            ["campaigns", `Campaigns (${campaigns.length})`],
            ["users", `Logins (${everyone.length})`],
            ["party", copy.settingsTab],
            ["areas", "Areas and register"],
            ["health", "Health"],
            ["audit", "Audit"],
            ["export", "Export"],
          ]}
        />

        {tab === "campaigns" && !aspirant && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <Btn onClick={() => navigate("/party/aspirants")}>New campaign</Btn>
            <span className="text-ui text-muted-foreground">
              A workspace is made from an approved aspirant, in Aspirants.
            </span>
          </div>
        )}
        {tab === "campaigns" && <OpenPartyWorkspace onInvite={handOut} />}

        {tab === "campaigns" &&
          (campaigns.length === 0 ? (
            <Card variant="outline">
              <span className="text-muted-foreground">
                No campaigns yet.
              </span>
            </Card>
          ) : (
            campaigns.map((c) => (
              <CampaignCard key={c.id} campaign={c} users={everyone} />
            ))
          ))}

        {tab === "party" && !aspirant && (
          <div>
            <Btn onClick={() => navigate("/party/aspirants")}>Open aspirants</Btn>
          </div>
        )}
        {tab === "party" && <PartySettings />}
        {tab === "areas" && <ReferenceData />}
        {tab === "health" && <Health />}
        {tab === "audit" && <AuditTrail />}
        {tab === "export" && <ExportPanel />}

        {tab === "users" && (
          <Card variant="outline" className="min-w-0">
            <FilterPills
              label="Show logins"
              value={roleFilter}
              onChange={(key) => {
                setRoleFilter(key);
                setFailed({});
              }}
              options={[
                ["", "Everyone"],
                ["manager", "Managers"],
                ["candidate", "Aspirants"],
                ["mobilizer", "Mobilizers"],
              ]}
            />
            <NewLogin campaigns={campaigns} create={create} />
            <div className="flex flex-col">
              {loginPages.isPending ? (
                <LoadingText>Loading the logins…</LoadingText>
              ) : listed.length === 0 ? (
                <p className="text-ui text-muted-foreground">
                  Nobody matches that.
                </p>
              ) : (
                listed.map((u) => (
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
            <LoadMore
              shown={listed.length}
              total={roleFilter ? undefined : everyone.length}
              noun="logins"
              hasMore={!!loginPages.hasNextPage}
              loading={loginPages.isFetchingNextPage}
              onMore={() => loginPages.fetchNextPage()}
            />
          </Card>
        )}
      </div>
    </Shell>
  );
}
