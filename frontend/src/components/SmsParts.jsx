// Pieces shared by the campaign's and the party's SMS pages.
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/input";
import { formatNumber, plural } from "@/lib/format";
import { DELIVERY_STATUS, partsOf } from "@/lib/sms";

/** The message box; `text` is the whole text as sent, footer included, for the length and part count. */
export function MessageField({ value, onChange, text }) {
  return (
    <Field label="Message" hint={<>{plural(text.length, "character")} · {plural(partsOf(text), "SMS part")} each · "Reply STOP to opt out" is added</>}>
      <Textarea rows={5} maxLength={895} value={value} onChange={(e) => onChange(e.target.value)} />
    </Field>
  );
}

/** A draft's optional reason box with Decline and Keep it. */
export function DeclineForm({ note, onNote, busy, onDecline, onKeep }) {
  return (
    <div className="flex flex-wrap items-end gap-2">
      <Field label="Why (optional)" className="min-w-0 flex-1"><Input value={note} onChange={(e) => onNote(e.target.value)} /></Field>
      <Button shape="rounded" size="sm" variant="outline" disabled={busy} onClick={onDecline}>Decline</Button>
      <Button shape="rounded" size="sm" variant="quiet" onClick={onKeep}>Keep it</Button>
    </div>
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
