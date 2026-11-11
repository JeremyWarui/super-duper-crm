// Requests from people about their personal data, for the party (no campaign) or one workspace:
// logged with the date the law gives, answered with a note of how.
import { useState } from "react";
import { useDataRequests, useLogDataRequest, useUpdateDataRequest } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/input";
import { formatDate, nairobiDate } from "@/lib/format";
import { ErrorText } from "@/components/ui/error-text";
import { LoadingText } from "@/components/ui/loading-text";
import { useForm } from "@/lib/form";

const KINDS = { access: "Access to their data", correction: "Correction", erasure: "Erasure" };
const DAYS = { access: 7, correction: 14, erasure: 14 };
const BLANK = { kind: "access", requester_name: "", requester_contact: "", details: "", received_on: "" };

function LogForm({ campaignId, onDone }) {
  const [form, , set] = useForm({ ...BLANK, received_on: nairobiDate() });
  const save = useLogDataRequest(campaignId);
  const submit = (e) => {
    e.preventDefault();
    save.mutate(form, { onSuccess: onDone });
  };
  return (
    <form onSubmit={submit} className="grid gap-3 border-t border-line pt-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Request">
          <select aria-label="Request" value={form.kind} onChange={set("kind")} className="min-h-11 w-full rounded-lg border border-line-control bg-white px-3">
            {Object.entries(KINDS).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
          </select>
        </Field>
        <Field label="Received on" hint={`Due ${DAYS[form.kind]} days later.`}>
          <Input type="date" value={form.received_on} onChange={set("received_on")} required />
        </Field>
        <Field label="Who asked"><Input value={form.requester_name} maxLength={150} onChange={set("requester_name")} required /></Field>
        <Field label="Phone or email to answer"><Input value={form.requester_contact} maxLength={254} onChange={set("requester_contact")} required /></Field>
      </div>
      <Field label="What they asked for"><Textarea rows={3} value={form.details} maxLength={4000} onChange={set("details")} /></Field>
      <ErrorText error={save.error} className="text-small" />
      <div className="flex gap-2">
        <Button type="submit" shape="rounded" disabled={save.isPending}>{save.isPending ? "Saving…" : "Log request"}</Button>
        <Button type="button" shape="rounded" variant="ghost" onClick={onDone}>Cancel</Button>
      </div>
    </form>
  );
}

function Answer({ campaignId, request }) {
  const [answer, setAnswer] = useState(request.answer);
  const [due, setDue] = useState(request.due_on);
  const save = useUpdateDataRequest(campaignId);
  const done = request.status === "done";
  return (
    <div className="grid gap-2">
      <Field label={`How it was answered: ${request.requester_name}`}>
        <Textarea rows={2} value={answer} maxLength={4000} disabled={done} onChange={(e) => setAnswer(e.target.value)} />
      </Field>
      <div className="flex flex-wrap items-end gap-2">
        {!done ? (
          <>
            <Field label={`Due date: ${request.requester_name}`} className="w-[190px]">
              <Input type="date" value={due} onChange={(e) => setDue(e.target.value)} />
            </Field>
            <Button size="sm" shape="rounded" variant="quiet" disabled={save.isPending} onClick={() => save.mutate({ id: request.id, answer, due_on: due })}>Save</Button>
            <Button size="sm" shape="rounded" disabled={save.isPending || !answer.trim()} onClick={() => save.mutate({ id: request.id, answer, status: "done" })}>Mark answered</Button>
          </>
        ) : (
          <Button size="sm" shape="rounded" variant="quiet" disabled={save.isPending} onClick={() => save.mutate({ id: request.id, status: "open" })}>Reopen</Button>
        )}
      </div>
      <ErrorText error={save.error} className="text-small" />
    </div>
  );
}

function Row({ campaignId, request }) {
  const [open, setOpen] = useState(false);
  const tone = request.status === "done" ? ["Answered", "ok"] : request.overdue ? ["Overdue", "bad"] : ["Open", "warn"];
  return (
    <li className="grid gap-2 border-t border-line py-3 first:border-t-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-semibold">{request.requester_name}</span>
        <span className="text-muted-foreground">{KINDS[request.kind]}</span>
        <Badge tone={tone[1]}>{tone[0]}</Badge>
        <span className="ml-auto text-small text-muted-foreground tabular-nums">
          {request.status === "done" ? `Answered ${formatDate(request.answered_at)}` : `Due ${formatDate(request.due_on)}`}
        </span>
      </div>
      <p className="text-small text-muted-foreground">
        {request.requester_contact} · received {formatDate(request.received_on)}{request.details ? ` · ${request.details}` : ""}
      </p>
      {open ? <Answer campaignId={campaignId} request={request} /> : (
        <Button size="sm" shape="rounded" variant="quiet" className="justify-self-start" onClick={() => setOpen(true)}>
          {request.status === "done" ? "See the answer" : "Answer"}
        </Button>
      )}
    </li>
  );
}

/** The request log and its form; `campaignId` undefined is the party's own. */
export default function DataRequests({ campaignId }) {
  const list = useDataRequests(campaignId);
  const [adding, setAdding] = useState(false);
  const rows = list.data || [];
  const overdue = rows.filter((r) => r.overdue).length;
  return (
    <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Data requests">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-display text-[18px] font-bold">Data requests</h2>
        {overdue ? <Badge tone="bad">{overdue} overdue</Badge> : null}
        {!adding ? <Button size="sm" shape="rounded" className="ml-auto" onClick={() => setAdding(true)}>Log a request</Button> : null}
      </div>
      <p className="text-small text-muted-foreground">
        Requests to see, correct or erase someone's details. The law gives 7 days to answer access and 14 for correction or erasure.
      </p>
      {adding ? <LogForm campaignId={campaignId} onDone={() => setAdding(false)} /> : null}
      {list.isLoading ? <LoadingText /> : null}
      <ErrorText error={list.error} />
      {list.data ? (
        rows.length ? <ul className="grid">{rows.map((r) => <Row key={r.id} campaignId={campaignId} request={r} />)}</ul>
          : <p className="text-muted-foreground">No requests yet.</p>
      ) : null}
    </Card>
  );
}
