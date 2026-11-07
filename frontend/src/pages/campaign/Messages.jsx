// Texts to the campaign's supporters: Comms and Coordinators draft, the Candidate or Manager
// approves and sends, and the delivery log shows what the gateway reported.
import { useState } from "react";
import { useDeclineMessage, useDeleteMessage, useDraftMessage, useMessageLog, useMessageReach, useMessages, useSendMessage } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/input";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useDraft } from "@/lib/draft";
import { formatDate, formatNumber as fmt, plural } from "@/lib/format";
import { DELIVERY_STATUS, FOOTER, partsOf } from "@/lib/sms";
import { cn } from "@/lib/utils";
import SendError from "./SendError";
import WsHeader, { KitError, KitLoading } from "./WsHeader";

export default function Messages({ campaign }) {
  const page = useMessages(campaign.id);
  const data = page.data;
  return (
    <>
      <WsHeader context="Reach out" title="Messages" sub={data ? senderLine(data) : "SMS to your supporters."} />
      {page.isLoading && <KitLoading />}
      {page.error && <KitError error={page.error} />}
      {data && (
        <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
          <Compose campaign={campaign} data={data} />
          <div className="grid min-w-0 content-start gap-4">
            <Drafts data={data} />
            <History data={data} />
          </div>
        </div>
      )}
    </>
  );
}

function senderLine(data) {
  const from = data.sender_id ? `SMS from sender ID ${data.sender_id}` : "SMS from the shared short code";
  return data.provider === "console" ? `${from} · practice mode: texts are logged, not sent` : from;
}

function Compose({ campaign, data }) {
  const [form, setForm, clear] = useDraft(`message:${campaign.id}`, { body: "", wards: [] });
  const [confirming, setConfirming] = useState(false);
  const [done, setDone] = useState(null);
  const reach = useMessageReach(campaign.id, form.wards);
  const save = useDraftMessage();
  const text = form.body.trim() + FOOTER;
  const parts = partsOf(text);
  const count = reach.data?.recipients ?? null;
  const ready = form.body.trim().length > 0 && text.length <= 918 && !save.isPending;

  const change = (patch) => { setForm((f) => ({ ...f, ...patch })); setConfirming(false); setDone(null); };
  const toggle = (id) => change({ wards: form.wards.includes(id) ? form.wards.filter((w) => w !== id) : [...form.wards, id] });
  const submit = (send) =>
    save.mutate(
      { campaign: campaign.id, body: form.body.trim(), wards: form.wards, send },
      { onSuccess: (m) => { clear(); setConfirming(false); setDone(send ? `Sent to ${plural(m.recipients, "supporter")}.` : "Saved. The candidate or manager sends it."); } },
    );

  return (
    <Card variant="outline" className="min-w-0 content-start gap-4" role="region" aria-label="New SMS">
      <h2 className="text-h3 font-bold">New SMS</h2>
      <div className="grid gap-2">
        <span className="text-small font-semibold" id="send-to">Send to</span>
        <div role="group" aria-labelledby="send-to" className="flex flex-wrap gap-2">
          <Pill on={form.wards.length === 0} onClick={() => change({ wards: [] })}>{data.wards.length === 1 ? data.wards[0].name : "All my wards"}</Pill>
          {data.wards.length > 1 && data.wards.map((w) => (
            <Pill key={w.id} on={form.wards.includes(w.id)} onClick={() => toggle(w.id)}>{w.name}</Pill>
          ))}
        </div>
        <p className="text-small text-muted-foreground" aria-live="polite">
          {count === null ? "Counting…" : (
            <>
              <strong className="text-ink">{plural(count, "recipient")}</strong>: supporters who agreed to hear from this campaign
              {reach.data.opted_out > 0 && `. ${plural(reach.data.opted_out, "person", "people")} who opted out ${reach.data.opted_out === 1 ? "is" : "are"} left out`}
              {reach.data.no_number > 0 && `. ${plural(reach.data.no_number, "number")} unusable`}.
            </>
          )}
        </p>
        {data.wards.length === 0 && <p className="text-small text-muted-foreground">No supporter has agreed to texts yet.</p>}
      </div>

      <Field label="Message" hint={<>{plural(text.length, "character")} · {plural(parts, "SMS part")} each · "Reply STOP to opt out" is added</>}>
        <Textarea rows={5} maxLength={895} value={form.body} onChange={(e) => change({ body: e.target.value })} />
      </Field>

      {save.error && <SendError error={save.error} onRetry={() => submit(confirming)} />}
      {done && <p role="status" className="font-semibold text-ok-foreground">{done}</p>}

      <div className="flex flex-wrap items-center gap-2">
        {data.can_send ? (
          confirming ? (
            <>
              <Button shape="rounded" disabled={!ready} onClick={() => submit(true)}>{save.isPending ? "Sending…" : `Send to ${plural(count ?? 0, "person", "people")}`}</Button>
              <Button shape="rounded" variant="quiet" onClick={() => setConfirming(false)}>Not yet</Button>
            </>
          ) : (
            <>
              <Button shape="rounded" disabled={!ready || !count} onClick={() => setConfirming(true)}>Send SMS</Button>
              <Button shape="rounded" variant="outline" disabled={!ready} onClick={() => submit(false)}>Save draft</Button>
            </>
          )
        ) : (
          <Button shape="rounded" disabled={!ready} onClick={() => submit(false)}>{save.isPending ? "Saving…" : "Send for approval"}</Button>
        )}
      </div>
      <p className="text-small text-muted-foreground">SMS only: WhatsApp's business platform doesn't allow political messaging. Messages go only to people who agreed to hear from this campaign.</p>
    </Card>
  );
}

function Pill({ on, onClick, children }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cn("min-h-10 cursor-pointer rounded-full border-[1.5px] px-4 text-ui font-semibold max-sm:min-h-11", on ? "border-ink bg-ink text-white" : "border-line-control bg-white text-ink")}
    >
      {children}
    </button>
  );
}

function Drafts({ data }) {
  const drafts = data.messages.filter((m) => m.status === "draft");
  const approve = useSendMessage();
  const decline = useDeclineMessage();
  const remove = useDeleteMessage();
  const [declining, setDeclining] = useState(null);
  const [note, setNote] = useState("");
  if (drafts.length === 0) return null;
  const busy = approve.isPending || decline.isPending || remove.isPending;
  const failed = approve.error || decline.error || remove.error;
  return (
    <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Waiting for approval">
      <h2 className="text-h3 font-bold">Waiting for approval</h2>
      {failed && <p role="alert" className="font-semibold text-destructive">{failed.message}</p>}
      {drafts.map((m) => (
        <article key={m.id} className="grid gap-2 rounded-lg border border-line p-3" aria-label={`Draft by ${m.drafted_by}`}>
          <p className="whitespace-pre-wrap">{m.body}</p>
          <p className="text-small text-muted-foreground">{m.drafted_by} · {formatDate(m.created_at)} · {wardsOf(m)}</p>
          {declining === m.id ? (
            <div className="flex flex-wrap items-end gap-2">
              <Field label="Why (optional)" className="min-w-0 flex-1"><Input value={note} onChange={(e) => setNote(e.target.value)} /></Field>
              <Button shape="rounded" size="sm" variant="outline" disabled={busy} onClick={() => decline.mutate({ id: m.id, note }, { onSuccess: () => { setDeclining(null); setNote(""); } })}>Decline</Button>
              <Button shape="rounded" size="sm" variant="quiet" onClick={() => setDeclining(null)}>Keep it</Button>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {data.can_send && <Button shape="rounded" size="sm" disabled={busy} onClick={() => approve.mutate(m.id)}>Approve and send</Button>}
              {data.can_send && <Button shape="rounded" size="sm" variant="outline" disabled={busy} onClick={() => setDeclining(m.id)}>Decline…</Button>}
              {(m.mine || data.can_send) && <Button shape="rounded" size="sm" variant="quiet" disabled={busy} onClick={() => remove.mutate(m.id)}>Delete</Button>}
            </div>
          )}
        </article>
      ))}
    </Card>
  );
}

const wardsOf = (m) => (m.ward_names.length ? m.ward_names.join(", ") : "all wards");

function History({ data }) {
  const done = data.messages.filter((m) => m.status !== "draft");
  const [open, setOpen] = useState(null);
  return (
    <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Sent">
      <h2 className="text-h3 font-bold">Sent</h2>
      {done.length === 0 && <p className="text-muted-foreground">Nothing sent yet.</p>}
      {done.map((m) => (
        <article key={m.id} className="grid gap-2 border-b border-line pb-3 last:border-0 last:pb-0">
          <p className="line-clamp-2 font-semibold">{m.body}</p>
          <p className="text-small text-muted-foreground">
            {formatDate(m.decided_at || m.created_at)} · {wardsOf(m)} · {m.status === "declined" ? `declined by ${m.decided_by}` : `${plural(m.recipients, "recipient")}, sent by ${m.decided_by}`}
          </p>
          {m.status === "declined" ? (
            <div><Badge tone="stone">Declined</Badge>{m.note && <span className="ml-2 text-small">{m.note}</span>}</div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              {Object.entries(DELIVERY_STATUS).map(([key, [label, tone]]) => m.delivery[key] > 0 && <Badge key={key} tone={tone}>{label} {fmt(m.delivery[key])}</Badge>)}
              {data.can_send && (
                <Button shape="rounded" size="sm" variant="quiet" aria-expanded={open === m.id} onClick={() => setOpen(open === m.id ? null : m.id)}>
                  {open === m.id ? "Hide delivery log" : "Delivery log"}
                </Button>
              )}
            </div>
          )}
          {open === m.id && <DeliveryLog id={m.id} />}
        </article>
      ))}
    </Card>
  );
}

function DeliveryLog({ id }) {
  const log = useMessageLog(id);
  if (log.isLoading) return <KitLoading />;
  if (log.error) return <KitError error={log.error} />;
  return (
    <Table stack minWidth={420}>
      <THead><TR><TH>Number</TH><TH>Status</TH><TH>Detail</TH></TR></THead>
      <TBody>
        {log.data.map((r) => (
          <TR key={r.phone}>
            <TD>{r.phone}</TD>
            <TD><Badge tone={(DELIVERY_STATUS[r.status] || ["", "stone"])[1]}>{(DELIVERY_STATUS[r.status] || [r.status])[0]}</Badge></TD>
            <TD className="text-muted-foreground">{r.detail || "None"}</TD>
          </TR>
        ))}
      </TBody>
    </Table>
  );
}
