// Texts to the campaign's contacts: Comms and Coordinators draft, the Candidate or Manager
// approves and sends, and the delivery log shows what the gateway reported.
import { useEffect, useState } from "react";
import { useDeclineMessage, useDeleteMessage, useDraftMessage, useDraftReach, useMessageLog, useMessageReach, useMessages, useRunAction, useSendMessage, useSendTestText, useSmsRuns, useTestTexts } from "@/api/hooks";
import { download } from "@/api/client";
import { ReasonForm } from "@/components/ui/confirm";
import { Card, CardTitle } from "@/components/ui/card";
import { Field, Input, NativeSelect } from "@/components/ui/input";
import { StatusText } from "@/components/ui/notice";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ComposePanel, DraftList, ReachLine, SentList } from "@/components/SmsParts";
import { FilterPills } from "@/components/ui/tabs";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useDraft } from "@/lib/draft";
import { formatDate, plural } from "@/lib/format";
import { SUPPORT_LEVELS } from "@/lib/labels";
import { composed, deliveryOf } from "@/lib/sms";
import SendError from "./SendError";
import { ErrorText } from "@/components/ui/error-text";
import { SlottedHeader } from "@/components/layout/AppPage";
import { LoadingText } from "@/components/ui/loading-text";

export default function Messages({ campaign }) {
  const page = useMessages(campaign.id);
  const data = page.data;
  return (
    <>
      <SlottedHeader context="Reach out" title="Messages" sub={data ? senderLine(data) : "SMS to your contacts."} />
      {page.isLoading && <LoadingText />}
      <ErrorText error={page.error} />
      {data && (
        <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
          <Compose campaign={campaign} data={data} />
          <div className="grid min-w-0 content-start gap-4">
            {data.can_send && <Runs campaign={campaign} />}
            {data.can_send && <TestText campaign={campaign} />}
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
  const [form, setForm, clear] = useDraft(`message:${campaign.id}`, { body: "", wards: [], language: "en", support_levels: DEFAULT_LEVELS });
  const [confirming, setConfirming] = useState(false);
  const [done, setDone] = useState(null);
  const levels = form.support_levels || DEFAULT_LEVELS;
  const reach = useMessageReach(campaign.id, form.wards, levels);
  const priced = useMessageReach(campaign.id, form.wards, levels, confirming ? form.body.trim() : "-");
  const save = useDraftMessage();
  const count = reach.data?.recipients ?? null;
  const opted = reach.data?.opted_out ?? 0;
  const unusable = reach.data?.no_number ?? 0;
  const ready = composed(form.body).fits && !save.isPending;

  const change = (patch) => { setForm((f) => ({ ...f, ...patch })); setConfirming(false); setDone(null); };
  const toggle = (id) => change({ wards: form.wards.includes(id) ? form.wards.filter((w) => w !== id) : [...form.wards, id] });
  const toggleLevel = (level) => change({ support_levels: levels.includes(level) ? levels.filter((l) => l !== level) : [...levels, level] });
  const submit = (send) =>
    save.mutate(
      { campaign: campaign.id, body: form.body.trim(), wards: form.wards, support_levels: levels, send, language: form.language || "en" },
      { onSuccess: (m) => { clear(); setConfirming(false); setDone(send ? `Approved for ${plural(m.recipients, "contact")}. It goes out in batches between 08:00 and 18:00.` : "Saved. The candidate or manager sends it."); } },
    );

  const picker = (
      <div className="grid gap-2">
        <span className="text-small font-semibold">Send to</span>
        <FilterPills
          label="Send to"
          options={[["", data.wards.length === 1 ? data.wards[0].name : "All my wards"], ...(data.wards.length > 1 ? data.wards.map((w) => [w.id, w.name]) : [])]}
          value={form.wards.length ? form.wards : [""]}
          onChange={(id) => (id ? toggle(id) : change({ wards: [] }))}
        />
        {data.wards.length === 0 && <p className="text-small text-muted-foreground">No contact has agreed to texts yet.</p>}
        <span className="mt-2 text-small font-semibold">Support level</span>
        <FilterPills label="Support levels" options={SUPPORT_LEVELS} value={levels} onChange={toggleLevel} />
        {levels.length === 0 && <p className="text-small text-muted-foreground">Pick at least one support level.</p>}
        <Field label="Language">
          <NativeSelect value={form.language || "en"} onChange={(e) => change({ language: e.target.value })}>
            {Object.entries(LANGUAGES).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </NativeSelect>
        </Field>
      </div>
  );
  const actions = (
      <div className="flex flex-wrap items-center gap-2">
        {data.can_send ? (
          confirming ? (
            <>
              <CostLine reach={priced} />
              <Button loading={save.isPending} disabled={!ready || priced.isPlaceholderData || !priced.data || priced.isError || priced.isFetching} onClick={() => submit(true)}>{save.isPending ? "Sending…" : `Send to ${plural(priced.data?.recipients ?? 0, "person", "people")}`}</Button>
              <Button variant="quiet" onClick={() => setConfirming(false)}>Not yet</Button>
            </>
          ) : (
            <>
              <Button disabled={!ready || !count || levels.length === 0} onClick={() => setConfirming(true)}>Send SMS</Button>
              <Button variant="outline" disabled={!ready || levels.length === 0} onClick={() => submit(false)}>Save draft</Button>
            </>
          )
        ) : (
          <Button loading={save.isPending} disabled={!ready || levels.length === 0} onClick={() => submit(false)}>{save.isPending ? "Saving…" : "Send for approval"}</Button>
        )}
      </div>
  );
  return (
    <ComposePanel
      title="New SMS"
      picker={picker}
      reach={<ReachLine count={count} who="contacts who agreed to receive texts" left={[
        opted > 0 && `${plural(opted, "person", "people")} who opted out ${opted === 1 ? "is" : "are"} left out`,
        unusable > 0 && `${plural(unusable, "number")} unusable`,
      ]} />}
      body={form.body}
      onBody={(body) => change({ body })}
      error={save.error && <SendError error={save.error} onRetry={() => submit(confirming)} />}
      done={done}
      actions={actions}
      note="SMS only: WhatsApp's business platform doesn't allow political messaging. Messages go only to people who agreed to receive texts from this campaign."
    />
  );
}

const LANGUAGES = { en: "English", sw: "Kiswahili" };
const DEFAULT_LEVELS = ["supporter", "undecided"];
const LEVEL_NAMES = Object.fromEntries(SUPPORT_LEVELS);
const levelsOf = (m) => (m.support_levels?.length ? m.support_levels.map((l) => LEVEL_NAMES[l] || l).join(", ") : "every support level");
const wardsOf = (m) => `${m.ward_names.length ? m.ward_names.join(", ") : "all wards"} · ${levelsOf(m)} · ${LANGUAGES[m.language] || "English"}`;

// What sending would cost: recipients × SMS parts × the price of one part.
function CostLine({ reach }) {
  if (reach.error) return <ErrorText error={reach.error} />;
  if (!reach.data || reach.isPlaceholderData) return <span className="w-full text-small text-muted-foreground">Working out the cost…</span>;
  const r = reach.data;
  return (
    <p className="w-full text-small font-semibold" role="status">
      {plural(r.recipients, "person", "people")} × {plural(r.parts, "SMS part")} · about {kes(r.estimated_cost_cents)}
    </p>
  );
}

// The confirm line for approving a draft, priced on the draft's own text and audience; `onReady`
// hears whether the price is on screen.
function DraftCost({ message, onReady }) {
  const reach = useDraftReach(message.id);
  const shown = !!reach.data && !reach.isPlaceholderData && !reach.error;
  useEffect(() => onReady(shown), [shown, onReady]);
  return <CostLine reach={reach} />;
}

function Drafts({ data }) {
  return (
    <DraftList
      cost={(m, ready) => <DraftCost message={m} onReady={ready} />}
      drafts={data.messages.filter((m) => m.status === "draft")}
      about={wardsOf}
      decide={() => data.can_send}
      canDelete={(m) => m.mine || data.can_send}
      approve={useSendMessage()}
      decline={useDeclineMessage()}
      remove={useDeleteMessage()}
    />
  );
}

function History({ data }) {
  return <SentList messages={data.messages.filter((m) => m.status !== "draft")} title="Sent" about={wardsOf} sentBy="sent by" Log={data.can_send ? DeliveryLog : null} />;
}

function DeliveryLog({ id }) {
  const log = useMessageLog(id);
  if (log.isLoading) return <LoadingText />;
  if (log.error) return <ErrorText error={log.error} />;
  return <LogTable rows={log.data} />;
}

function LogTable({ rows }) {
  return (
    <Table stack minWidth={420}>
      <THead><TR><TH>Number</TH><TH>Status</TH><TH>Detail</TH></TR></THead>
      <TBody>
        {rows.map((r) => {
          const [label, tone] = deliveryOf(r);
          return (
            <TR key={`${r.phone}-${r.created_at}`}>
              <TD>{r.phone}</TD>
              <TD><Badge tone={tone}>{label}</Badge></TD>
              <TD className="text-muted-foreground">{(r.status !== "sent" && r.detail) || "None"}</TD>
            </TR>
          );
        })}
      </TBody>
    </Table>
  );
}

// One text to one number, now; a live gateway only texts the campaign's own people.
function TestText({ campaign }) {
  const [form, setForm] = useState({ phone: "", body: "Test from the campaign CRM" });
  const send = useSendTestText();
  const log = useTestTexts(campaign.id);
  const submit = (e) => {
    e.preventDefault();
    send.mutate({ campaign: campaign.id, ...form });
  };
  return (
    <Card variant="outline" className="min-w-0 gap-3" role="region" aria-labelledby="test-sms-h">
      <CardTitle id="test-sms-h">Send test SMS</CardTitle>
      <form className="flex flex-col gap-3" onSubmit={submit}>
        <Field label="Phone number"><Input inputMode="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="0712 345678" /></Field>
        <Field label="Text"><Input value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} /></Field>
        <Button type="submit" className="self-start" loading={send.isPending} disabled={send.isPending || !form.phone.trim() || !form.body.trim()}>Send test SMS</Button>
      </form>
      {send.isSuccess && <StatusText>{send.data.message}</StatusText>}
      <ErrorText error={send.error} />
      {log.data?.length > 0 && <LogTable rows={log.data} />}
    </Card>
  );
}

const STAGE = {
  awaiting_vetting: ["Waiting for vetting", "warn"],
  scheduled: ["Waiting for the window", "info"],
  sending: ["Sending", "info"],
  paused: ["Paused", "warn"],
  halted: ["Halted", "bad"],
  completed: ["Completed", "ok"],
};
const kes = (cents) => `KES ${(cents / 100).toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const timeOf = (iso) => new Date(iso).toLocaleTimeString("en-KE", { hour: "2-digit", minute: "2-digit", timeZone: "Africa/Nairobi" });

// Approved texts on their way out, a batch at a time, with Pause, Resume and Halt.
function Runs({ campaign }) {
  const runs = useSmsRuns(campaign.id);
  const act = useRunAction(campaign.id);
  if (!runs.data?.length) return null;
  return (
    <Card variant="outline" className="min-w-0 gap-3" role="region" aria-labelledby="runs-h">
      <CardTitle id="runs-h">Bulk sends</CardTitle>
      <ErrorText error={act.error} />
      {runs.data.map((r) => <Run key={r.id} campaign={campaign} run={r} act={act} />)}
    </Card>
  );
}

function Run({ campaign, run, act }) {
  const [halting, setHalting] = useState(false);
  const [reason, setReason] = useState("");
  const [label, tone] = STAGE[run.status] || [run.status, "stone"];
  const busy = act.isPending;
  const go = (action, body) => act.mutate({ id: run.id, action, body }, { onSuccess: () => setHalting(false) });
  const counts = [
    ["Targeted", run.targeted], ["Sent", run.sent], ["Delivered", run.delivered], ["Failed", run.failed],
    ["No consent", run.excluded_no_consent], ["Opted out", run.excluded_opted_out],
  ];
  return (
    <article className="grid gap-2 rounded-lg border border-line p-3" aria-label={`Bulk send of ${formatDate(run.created_at)}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Badge tone={tone}>{label}</Badge>
        <span className="text-small text-muted-foreground">{formatDate(run.created_at)} · {LANGUAGES[run.language]} · {plural(run.segments, "part")}</span>
      </div>
      <p className="line-clamp-2 text-small">{run.text}</p>
      {run.status === "scheduled" && run.waiting_until && <p className="text-small font-semibold">Waiting until {timeOf(run.waiting_until)}.</p>}
      {run.status === "halted" && <p className="text-small text-bad-foreground">Halted: {run.halt_reason}</p>}
      <dl className="grid grid-cols-3 gap-2 sm:grid-cols-6">
        {counts.map(([name, value]) => (
          <div key={name}><dt className="text-small text-muted-foreground">{name}</dt><dd className="font-bold tabular-nums">{value.toLocaleString("en-KE")}</dd></div>
        ))}
      </dl>
      <p className="text-small text-muted-foreground">Estimated {kes(run.estimated_cost_cents)} · spent {kes(run.actual_cost_cents)}</p>
      {halting ? (
        <ReasonForm visibleLabel label="Why halt it?" min={1} value={reason} onChange={setReason} yes="Halt" no="Keep sending" busy={busy}
          onNo={() => setHalting(false)} onYes={() => go("halt", { reason })} />
      ) : (
        <div className="flex flex-wrap gap-2">
          {["sending", "scheduled"].includes(run.status) && <Button size="sm" variant="outline" disabled={busy} onClick={() => go("pause")}>Pause</Button>}
          {run.status === "paused" && <Button size="sm" disabled={busy} onClick={() => go("resume")}>Resume</Button>}
          {!["halted", "completed"].includes(run.status) && <Button size="sm" variant="quiet" disabled={busy} onClick={() => setHalting(true)}>Halt…</Button>}
          <Button size="sm" variant="quiet" onClick={() => download(`/campaigns/${campaign.id}/sms-runs/${run.id}/consent.csv`, `sms-run-${run.id}-consent.csv`)}>Consent evidence (CSV)</Button>
        </div>
      )}
    </article>
  );
}
