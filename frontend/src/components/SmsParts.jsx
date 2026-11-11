// Pieces shared by the campaign's and the party's SMS pages.
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ReasonForm } from "@/components/ui/confirm";
import { ErrorText } from "@/components/ui/error-text";
import { Field, Textarea } from "@/components/ui/input";
import { formatDate, formatNumber, plural } from "@/lib/format";
import { BODY_MAX, composed, DELIVERY_STATUS, partsOf } from "@/lib/sms";

/** The message box; `text` is the whole text as sent, footer included, for the length and part count. */
export function MessageField({ value, onChange, text }) {
  return (
    <Field label="Message" hint={<>{plural(text.length, "character")} · {plural(partsOf(text), "SMS part")} each · "Reply STOP to opt out" is added</>}>
      <Textarea rows={5} maxLength={BODY_MAX} value={value} onChange={(e) => onChange(e.target.value)} />
    </Field>
  );
}

/** A declined text's badge and the approver's note. */
export function DeclinedNote({ note }) {
  return <div><Badge tone="stone">Declined</Badge>{note && <span className="ml-2 text-small">{note}</span>}</div>;
}

/** One badge per delivery state with any texts in it, e.g. "Delivered 120". */
export function DeliveryBadges({ delivery }) {
  return Object.entries(DELIVERY_STATUS).map(([key, [label, tone]]) => delivery[key] > 0 && <Badge key={key} tone={tone}>{label} {formatNumber(delivery[key])}</Badge>);
}

/**
 * Drafts waiting for approval. `about(m)` is the line under each text; `decide(m)` is true for the
 * Approve and Decline buttons, false for none, or a note to show instead; `canDelete(m)` adds Delete.
 */
export function DraftList({ drafts, about, decide, approve, decline, remove, canDelete = () => false }) {
  const [declining, setDeclining] = useState(null);
  const [note, setNote] = useState("");
  if (drafts.length === 0) return null;
  const busy = approve.isPending || decline.isPending || !!remove?.isPending;
  return (
    <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Waiting for approval">
      <h2 className="text-h3 font-bold">Waiting for approval</h2>
      <ErrorText error={approve.error || decline.error || remove?.error} />
      {drafts.map((m) => {
        const may = decide(m);
        return (
          <article key={m.id} className="grid gap-2 rounded-lg border border-line p-3" aria-label={`Draft by ${m.drafted_by}`}>
            <p className="whitespace-pre-wrap">{m.body}</p>
            <p className="text-small text-muted-foreground">{m.drafted_by} · {formatDate(m.created_at)} · {about(m)}</p>
            {typeof may === "string" ? (
              <p className="text-small text-muted-foreground">{may}</p>
            ) : declining === m.id ? (
              <ReasonForm visibleLabel label="Why (optional)" min={0} value={note} onChange={setNote} yes="Decline" no="Keep it" busy={busy} onNo={() => setDeclining(null)}
                onYes={() => decline.mutate({ id: m.id, note }, { onSuccess: () => { setDeclining(null); setNote(""); } })} />
            ) : may || canDelete(m) ? (
              <div className="flex flex-wrap gap-2">
                {may && <Button shape="rounded" size="sm" disabled={busy} onClick={() => approve.mutate(m.id)}>Approve and send</Button>}
                {may && <Button shape="rounded" size="sm" variant="outline" disabled={busy} onClick={() => setDeclining(m.id)}>Decline…</Button>}
                {canDelete(m) && <Button shape="rounded" size="sm" variant="quiet" disabled={busy} onClick={() => remove.mutate(m.id)}>Delete</Button>}
              </div>
            ) : null}
          </article>
        );
      })}
    </Card>
  );
}

/**
 * Texts sent or declined. `about(m)` is where each went; `sentBy` goes before the sender's name ("sent by");
 * `Log`, when given, is a delivery log component opened from each sent text.
 */
export function SentList({ messages, title, about, sentBy, Log }) {
  const [open, setOpen] = useState(null);
  return (
    <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label={title}>
      <h2 className="text-h3 font-bold">{title}</h2>
      {messages.length === 0 && <p className="text-muted-foreground">Nothing sent yet.</p>}
      {messages.map((m) => (
        <article key={m.id} className="grid gap-2 border-b border-line pb-3 last:border-0 last:pb-0">
          <p className="line-clamp-2 font-semibold">{m.body}</p>
          <p className="text-small text-muted-foreground">
            {formatDate(m.decided_at || m.created_at)} · {about(m)} · {m.status === "declined" ? `declined by ${m.decided_by}` : `${plural(m.recipients, "recipient")}, ${sentBy} ${m.decided_by}`}
          </p>
          {m.status === "declined" ? (
            <DeclinedNote note={m.note} />
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <DeliveryBadges delivery={m.delivery} />
              {Log && (
                <Button shape="rounded" size="sm" variant="quiet" aria-expanded={open === m.id} onClick={() => setOpen(open === m.id ? null : m.id)}>
                  {open === m.id ? "Hide delivery log" : "Delivery log"}
                </Button>
              )}
            </div>
          )}
          {Log && open === m.id && <Log id={m.id} />}
        </article>
      ))}
    </Card>
  );
}

/** How many a text reaches: "Counting…" until known, then the count, `who` they are and each of `left` left out. */
export function ReachLine({ count, who, left = [] }) {
  return (
    <p className="text-small text-muted-foreground" aria-live="polite">
      {count === null ? "Counting…" : (
        <><strong className="text-ink">{plural(count, "recipient")}</strong>: {who}{left.filter(Boolean).map((l) => `. ${l}`).join("")}.</>
      )}
    </p>
  );
}

/**
 * The new-text card: `picker` chooses who gets it, `reach` says how many, then the message box,
 * `error`, the `done` confirmation, the `actions` and a closing `note`.
 */
export function ComposePanel({ title, picker, reach, body, onBody, error, done, actions, note }) {
  return (
    <Card variant="outline" className="min-w-0 content-start gap-4" role="region" aria-label={title}>
      <h2 className="text-h3 font-bold">{title}</h2>
      {picker}
      {reach}
      <MessageField value={body} onChange={onBody} text={composed(body).text} />
      {error}
      {done && <p role="status" className="font-semibold text-ok-foreground">{done}</p>}
      {actions}
      <p className="text-small text-muted-foreground">{note}</p>
    </Card>
  );
}
