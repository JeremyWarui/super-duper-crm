// The console's Campaigns tab: each campaign's card, and opening the party's own workspace.
import { useState } from "react";
import { isEmail } from "@/lib/email";
import { isUsername } from "@/lib/username";
import { useAddMember, useDeleteCampaign, useOpenPartyWorkspace, usePartyWorkspace, useRenameCampaign, useRemoveMember } from "@/api/hooks";
import { useInstall } from "@/app/site";
import { formatNumber as fmt } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { ErrorText } from "@/components/ui/error-text";
import { Input, NativeSelect } from "@/components/ui/input";
import LoginFields from "@/components/LoginFields";
import { Pill, INLINE, Help, Danger } from "./kit";

export function CampaignCard({ campaign, users }) {
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
              <Button size="sm"
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
              </Button>
              <Button size="sm" variant="quiet" onClick={() => setRenaming(false)}>Cancel</Button>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle className="break-words">{campaign.title}</CardTitle>
              <Button size="sm" variant="quiet"
                onClick={() => {
                  setTitle(campaign.title);
                  setRenaming(true);
                }}
              >
                Rename
              </Button>
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
            <Button size="sm"
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
            </Button>
            <Button size="sm" variant="quiet" onClick={() => setAdding(false)}>Cancel</Button>
          </div>
        ) : (
          <Button size="sm" variant="quiet" onClick={() => setAdding(true)}>Add somebody</Button>
        )}
      </div>
    </Card>
  );
}

const NO_MANAGER = { username: "", first_name: "", last_name: "", email: "", phone: "" };
// A party copy's own workspace when setup did not open it; gone once it exists.
export function OpenPartyWorkspace({ onInvite }) {
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
        <Button size="sm" variant="quiet" onClick={() => setAsking(true)}>{title}</Button>
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
      <CardTitle>{title}</CardTitle>
      <div className="grid gap-3 sm:grid-cols-2">
        <LoginFields fields={["username", "first_name", "last_name", "email", "phone"]} form={form} set={(key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))} />
      </div>
      <Help>
        {replace
          ? `${sitting || "The sitting Workspace Manager"} is turned off and signed out. This person takes over and is emailed a link to choose their password.`
          : "The party's own national workspace, with every ward as a target. This person is its first Workspace Manager and is emailed a link to choose their password. There is only one party workspace."}
      </Help>
      <ErrorText error={open.error} className="text-ui" />
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="primary" disabled={!ready || open.isPending} onClick={submit}>
          {open.isPending ? (replace ? "Replacing…" : "Opening…") : replace ? "Replace" : "Open it"}
        </Button>
        <Button size="sm" variant="quiet" onClick={() => setAsking(false)}>Cancel</Button>
      </div>
    </Card>
  );
}
