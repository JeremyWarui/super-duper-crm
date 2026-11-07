// The party office's texts to members and volunteers: the Comms Officer drafts, the Party Super
// Admin approves and sends, and only people whose consent covers SMS receive one.
import { useState } from "react";
import { useDeclinePartyMessage, useDraftPartyMessage, usePartyMessageReach, usePartyMessages, usePartyPlaces, useSendPartyMessage } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/input";
import { formatDate, formatNumber as fmt, plural } from "@/lib/format";
import { DELIVERY_STATUS, FOOTER, partsOf } from "@/lib/sms";
import { cn } from "@/lib/utils";

const AUDIENCES = [
  ["members", "Members", "members who ticked SMS updates when they joined"],
  ["volunteers", "Volunteers", "active volunteers who chose SMS as their contact"],
];
const WHO = Object.fromEntries(AUDIENCES.map(([k, l]) => [k, l.toLowerCase()]));

export default function Messages() {
  const page = usePartyMessages();
  if (page.isLoading) return <p className="text-muted-foreground">Loading…</p>;
  if (page.error) return <p role="alert">{page.error.message}</p>;
  const data = page.data;
  return (
    <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <Compose />
      <div className="grid min-w-0 content-start gap-4">
        <Drafts data={data} />
        <History data={data} />
      </div>
    </div>
  );
}

function Select({ label, value, onChange, options, blank, disabled }) {
  return (
    <Field label={label} className="min-w-0 flex-[1_1_160px]">
      <select aria-label={label} className="min-h-11 w-full rounded-lg border border-line-control bg-white px-3" value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
        <option value="">{blank}</option>
        {options.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
      </select>
    </Field>
  );
}

function Compose() {
  const [audience, setAudience] = useState("members");
  const [county, setCounty] = useState("");
  const [constituency, setConstituency] = useState("");
  const [ward, setWard] = useState("");
  const [body, setBody] = useState("");
  const [done, setDone] = useState("");
  const counties = usePartyPlaces().data || [];
  const constituencies = usePartyPlaces({ county, enabled: !!county }).data || [];
  const wards = usePartyPlaces({ constituency, enabled: !!constituency }).data || [];
  const place = { audience, county: county || null, constituency: constituency || null, ward: ward || null };
  const reach = usePartyMessageReach(place);
  const save = useDraftPartyMessage();
  const text = body.trim() + FOOTER;
  const count = reach.data?.recipients ?? null;
  const ready = body.trim().length > 0 && text.length <= 918 && !save.isPending;
  const touch = (fn) => (v) => { fn(v); setDone(""); };

  return (
    <Card variant="outline" className="min-w-0 content-start gap-4" role="region" aria-label="New message">
      <h2 className="text-h3 font-bold">New message</h2>
      <div className="grid gap-2">
        <span className="text-small font-semibold" id="audience">Audience</span>
        <div role="group" aria-labelledby="audience" className="flex flex-wrap gap-2">
          {AUDIENCES.map(([key, label]) => (
            <button key={key} type="button" aria-pressed={audience === key} onClick={() => touch(setAudience)(key)}
              className={cn("min-h-11 rounded-full border-[1.5px] px-4 text-ui font-semibold", audience === key ? "border-ink bg-ink text-white" : "border-line-control bg-white text-ink")}>
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap gap-3">
        <Select label="County" value={county} blank="All counties" options={counties} onChange={touch((v) => { setCounty(v); setConstituency(""); setWard(""); })} />
        <Select label="Constituency" value={constituency} blank="All" options={constituencies} disabled={!county} onChange={touch((v) => { setConstituency(v); setWard(""); })} />
        <Select label="Ward" value={ward} blank="All" options={wards} disabled={!constituency} onChange={touch(setWard)} />
      </div>
      <p className="text-small text-muted-foreground" aria-live="polite">
        {count === null ? "Counting…" : (
          <>
            <strong className="text-ink">{plural(count, "recipient")}</strong>: {AUDIENCES.find(([k]) => k === audience)[2]}
            {reach.data.opted_out > 0 && `. ${plural(reach.data.opted_out, "number")} that replied STOP ${reach.data.opted_out === 1 ? "is" : "are"} left out`}.
          </>
        )}
      </p>
      <Field label="Message" hint={<>{plural(text.length, "character")} · {plural(partsOf(text), "SMS part")} each · "Reply STOP to opt out" is added</>}>
        <Textarea rows={5} maxLength={895} value={body} onChange={(e) => touch(setBody)(e.target.value)} />
      </Field>
      {save.error && <p role="alert" className="font-semibold text-destructive">{save.error.message}</p>}
      {done && <p role="status" className="font-semibold text-ok-foreground">{done}</p>}
      <Button shape="rounded" className="self-start" disabled={!ready}
        onClick={() => save.mutate({ ...place, body: body.trim() }, { onSuccess: () => { setBody(""); setDone("Saved. The Party Super Admin approves it before it is sent."); } })}>
        {save.isPending ? "Saving…" : "Send for approval"}
      </Button>
      <p className="text-small text-muted-foreground">Nothing is sent until the Party Super Admin approves it, and never by whoever drafted it.</p>
    </Card>
  );
}

function Drafts({ data }) {
  const drafts = data.messages.filter((m) => m.status === "draft");
  const approve = useSendPartyMessage();
  const decline = useDeclinePartyMessage();
  const [declining, setDeclining] = useState(null);
  const [note, setNote] = useState("");
  if (drafts.length === 0) return null;
  const busy = approve.isPending || decline.isPending;
  const failed = approve.error || decline.error;
  return (
    <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Waiting for approval">
      <h2 className="text-h3 font-bold">Waiting for approval</h2>
      {failed && <p role="alert" className="font-semibold text-destructive">{failed.message}</p>}
      {drafts.map((m) => (
        <article key={m.id} className="grid gap-2 rounded-lg border border-line p-3" aria-label={`Draft by ${m.drafted_by}`}>
          <p className="whitespace-pre-wrap">{m.body}</p>
          <p className="text-small text-muted-foreground">{m.drafted_by} · {formatDate(m.created_at)} · {WHO[m.audience]}, {m.place} · {plural(m.targeted, "recipient")} when drafted</p>
          {!data.can_send ? null : m.mine ? (
            <p className="text-small text-muted-foreground">Someone else approves your own draft.</p>
          ) : declining === m.id ? (
            <div className="flex flex-wrap items-end gap-2">
              <Field label="Why (optional)" className="min-w-0 flex-1"><Input value={note} onChange={(e) => setNote(e.target.value)} /></Field>
              <Button shape="rounded" size="sm" variant="outline" disabled={busy} onClick={() => decline.mutate({ id: m.id, note }, { onSuccess: () => { setDeclining(null); setNote(""); } })}>Decline</Button>
              <Button shape="rounded" size="sm" variant="quiet" onClick={() => setDeclining(null)}>Keep it</Button>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              <Button shape="rounded" size="sm" disabled={busy} onClick={() => approve.mutate(m.id)}>Approve and send</Button>
              <Button shape="rounded" size="sm" variant="outline" disabled={busy} onClick={() => setDeclining(m.id)}>Decline…</Button>
            </div>
          )}
        </article>
      ))}
    </Card>
  );
}

function History({ data }) {
  const done = data.messages.filter((m) => m.status !== "draft");
  return (
    <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Recent sends">
      <h2 className="text-h3 font-bold">Recent sends</h2>
      {done.length === 0 && <p className="text-muted-foreground">Nothing sent yet.</p>}
      {done.map((m) => (
        <article key={m.id} className="grid gap-2 border-b border-line pb-3 last:border-0 last:pb-0">
          <p className="line-clamp-2 font-semibold">{m.body}</p>
          <p className="text-small text-muted-foreground">
            {formatDate(m.decided_at || m.created_at)} · {WHO[m.audience]}, {m.place} · {m.status === "declined" ? `declined by ${m.decided_by}` : `${plural(m.recipients, "recipient")}, approved by ${m.decided_by}`}
          </p>
          {m.status === "declined" ? (
            <div><Badge tone="stone">Declined</Badge>{m.note && <span className="ml-2 text-small">{m.note}</span>}</div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {Object.entries(DELIVERY_STATUS).map(([key, [label, tone]]) => m.delivery[key] > 0 && <Badge key={key} tone={tone}>{label} {fmt(m.delivery[key])}</Badge>)}
            </div>
          )}
        </article>
      ))}
    </Card>
  );
}
