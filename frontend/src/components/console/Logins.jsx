// The console's Logins tab: a new login, and one row per login with its repairs.
import { useState } from "react";
import { isEmail } from "@/lib/email";
import { isUsername } from "@/lib/username";
import { PARTY_ROLES, PARTY_ROLE_LABEL } from "@/lib/labels";
import { useGrantPartyRole, useLinkPartyMember, useMemberSearch, useRevokePartyRole, useSetActive, useSetEmail } from "@/api/hooks";
import { useInstall } from "@/app/site";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { ErrorText } from "@/components/ui/error-text";
import { Field, Input, NativeSelect } from "@/components/ui/input";
import MemberSearch from "@/components/MemberSearch";
import LoginFields from "@/pages/campaign/LoginFields";
import { Pill, INLINE, Help, Danger } from "./kit";

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


export function NewLogin({ campaigns, create }) {
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
        <Button shape="rounded" size="sm" variant="quiet" onClick={() => setOpen(true)}>Add a login</Button>
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
      <CardTitle>A new login</CardTitle>

      <div className="grid gap-3 sm:grid-cols-2">
        <LoginFields fields={["username"]} form={form} set={(key) => (e) => set({ [key]: e.target.value })} />
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
        <LoginFields fields={["first_name", "last_name", "email", "phone"]} form={form} set={(key) => (e) => set({ [key]: e.target.value })} />
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
        <Button shape="rounded" size="sm" variant="primary" disabled={!ready || create.isPending} onClick={submit}>
          {create.isPending ? "Creating…" : "Create the login"}
        </Button>
        <Button shape="rounded" size="sm" variant="quiet"
          onClick={() => {
            setForm(BLANK);
            setOpen(false);
          }}
        >
          Cancel
        </Button>
      </div>
    </Card>
  );
}

// The party member a login belongs to; an office holder must be linked to an approved one.
function MemberLink({ user, onLinked }) {
  const link = useLinkPartyMember();
  const [q, setQ] = useState("");
  const [found, searching] = useMemberSearch(q, { status: "approved", limit: 5 });
  return (
    <div className="flex flex-col gap-1 text-small text-muted-foreground">
      {user.party_member ? (
        <span className="flex flex-wrap items-center gap-2">
          Party member: {user.party_member.full_name} ({user.party_member.status})
          {!user.party_roles?.length && (
            <Button shape="rounded" size="sm" variant="quiet"
              disabled={link.isPending}
              onClick={() => link.mutate({ user: user.id, member: null })}
            >
              Unlink
            </Button>
          )}
        </span>
      ) : (
        <MemberSearch
          label={`Party member for ${user.username}`}
          placeholder="Name or phone of an approved member"
          query={q}
          onQuery={setQ}
          results={searching ? found.data?.items || [] : undefined}
          loading={found.isFetching}
          empty="No approved member matches."
          picked={null}
          onPick={(m) => !link.isPending && link.mutate({ user: user.id, member: m.id }, { onSuccess: () => { setQ(""); onLinked(); } })}
        />
      )}
      <ErrorText error={link.isError && link.error} className="text-small" />
    </div>
  );
}

export function UserRow({ user, me, onReset, resetting, resetError }) {
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
              <Button shape="rounded" size="sm"
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
              </Button>
              <Button shape="rounded" size="sm" variant="quiet" onClick={() => setEditingEmail(false)}>Cancel</Button>
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
                    <Button shape="rounded" size="sm"
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
                    </Button>
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
            <Button shape="rounded" size="sm" variant="quiet"
              disabled={isMe || active.isPending}
              onClick={() => active.mutate({ id: user.id, active: true })}
            >
              Enable
            </Button>
          )}
        </div>
      </div>
      <ErrorText error={error} className="text-ui" />
    </div>
  );
}
