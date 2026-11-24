// Announcements: the leads write to the whole campaign, a ward or a centre; everyone reads what
// was sent to them, and the sender sees how many have read it.
import { useEffect, useState } from "react";
import { Megaphone } from "lucide-react";
import { useAnnouncements, useReadAnnouncements, useSendAnnouncement } from "@/api/hooks";
import { SlottedHeader } from "@/components/layout/AppPage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { ErrorText } from "@/components/ui/error-text";
import { Field, Input, Textarea } from "@/components/ui/input";
import { LoadingText } from "@/components/ui/loading-text";
import { formatDateTime } from "@/lib/format";
import { placeOf, UnitSelect, useUnitOptions } from "./UnitSelect";

const SENDERS = ["candidate", "manager", "comms", "coordinator"];

export default function Announcements({ campaign, role }) {
  const sender = SENDERS.includes(role);
  return (
    <>
      <SlottedHeader
        context="Reach out"
        title="Announcements"
        sub={sender ? "Tell the whole campaign, one ward or one centre. Each person gets it under the bell and as an alert, and you see who has read it." : "What the campaign has told your team."}
      />
      <div className={sender ? "grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]" : "grid min-w-0 gap-4"}>
        {sender ? <Compose campaign={campaign} required={role === "coordinator"} /> : null}
        <Feed campaign={campaign} />
      </div>
    </>
  );
}

function Compose({ campaign, required }) {
  const options = useUnitOptions(campaign);
  const send = useSendAnnouncement(campaign.id);
  const [form, setForm] = useState({ title: "", body: "", unit: "" });
  const ready = form.title.trim() && form.body.trim() && (!required || form.unit);
  const submit = (e) => {
    e.preventDefault();
    send.mutate(
      { title: form.title.trim(), body: form.body.trim(), ...placeOf(options, form.unit) },
      { onSuccess: () => setForm({ title: "", body: "", unit: form.unit }) },
    );
  };
  const sent = send.data;
  return (
    <Card variant="outline" className="min-w-0 content-start gap-4" role="region" aria-labelledby="compose-h">
      <CardTitle id="compose-h">New announcement</CardTitle>
      <form className="flex flex-col gap-3" onSubmit={submit}>
        <Field label="To">
          <UnitSelect campaign={campaign} options={options} value={form.unit} onChange={(unit) => setForm({ ...form, unit })} wholeCampaign={!required} aria-label="To" />
        </Field>
        <Field label="Title"><Input value={form.title} maxLength={120} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Briefing moved to 7 pm" /></Field>
        <Field label="Message">
          <Textarea value={form.body} maxLength={1000} rows={5} onChange={(e) => setForm({ ...form, body: e.target.value })} placeholder="What the team needs to know, and what to do." />
        </Field>
        <span aria-hidden className="-mt-1.5 text-small text-muted-foreground">{form.body.length} of 1000</span>
        <Button type="submit" className="self-start" loading={send.isPending} disabled={send.isPending || !ready}>
          <Megaphone className="size-4" aria-hidden /> Send announcement
        </Button>
      </form>
      <ErrorText error={send.error} />
      {sent ? (
        <p role="status" className="border-t border-line-soft pt-3 font-semibold">
          Sent to {sent.announcement.recipients} {sent.announcement.recipients === 1 ? "person" : "people"} in {sent.announcement.unit.toLowerCase() === "whole campaign" ? "the whole campaign" : sent.announcement.unit}
          {sent.alerted ? `; ${sent.alerted} ${sent.alerted === 1 ? "phone" : "phones"} alerted.` : "."}
        </p>
      ) : null}
    </Card>
  );
}

function Feed({ campaign }) {
  const list = useAnnouncements(campaign.id);
  const read = useReadAnnouncements(campaign.id);
  const unread = (list.data || []).some((a) => a.read_by_me === false);
  const { mutate } = read;
  useEffect(() => {
    if (unread) mutate();
  }, [unread, mutate]);
  return (
    <Card variant="outline" className="min-w-0 content-start gap-3" role="region" aria-labelledby="feed-h">
      <CardTitle id="feed-h">Recent announcements</CardTitle>
      {list.isLoading ? <LoadingText /> : null}
      <ErrorText error={list.error} />
      {list.data?.length === 0 ? <p className="text-ui text-muted-foreground">No announcements yet.</p> : null}
      <ul className="m-0 flex list-none flex-col gap-3 p-0">
        {(list.data || []).map((a) => (
          <li key={a.id} className="flex flex-col gap-2 rounded-photo border border-line-soft bg-white p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-body font-bold">{a.title}</span>
              {a.read_by_me === false ? <Badge tone="ok">New</Badge> : null}
              <Badge tone="stone">{a.unit}</Badge>
            </div>
            <p className="whitespace-pre-line text-ui text-text-2">{a.body}</p>
            <div className="flex flex-wrap items-center justify-between gap-2 text-small text-muted-foreground">
              <span>{a.author} · {formatDateTime(a.created_at)}</span>
              {a.recipients != null ? <Receipt read={a.read} of={a.recipients} /> : null}
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** "Read by 3 of 5" with a bar. */
function Receipt({ read, of }) {
  const share = of ? Math.round((100 * read) / of) : 0;
  return (
    <span className="flex items-center gap-2 font-semibold text-ink">
      <span aria-hidden className="h-1.5 w-20 overflow-hidden rounded-full bg-stone">
        <span className="block h-full rounded-full bg-primary" style={{ width: `${share}%` }} />
      </span>
      Read by {read} of {of}
    </span>
  );
}
