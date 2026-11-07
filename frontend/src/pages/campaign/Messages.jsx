// Texts to the campaign's supporters: Comms and Coordinators draft, the Candidate or Manager
// approves and sends, and the delivery log shows what the gateway reported.
import { useState } from "react";
import { useDeclineMessage, useDeleteMessage, useDraftMessage, useMessageLog, useMessageReach, useMessages, useSendMessage } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DraftList, MessageField, SentList } from "@/components/SmsParts";
import { FilterPills } from "@/components/ui/tabs";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useDraft } from "@/lib/draft";
import { plural } from "@/lib/format";
import { DELIVERY_STATUS, FOOTER } from "@/lib/sms";
import SendError from "./SendError";
import WsHeader, { KitLoading } from "./WsHeader";
import { ErrorText } from "@/components/ui/error-text";

export default function Messages({ campaign }) {
  const page = useMessages(campaign.id);
  const data = page.data;
  return (
    <>
      <WsHeader context="Reach out" title="Messages" sub={data ? senderLine(data) : "SMS to your supporters."} />
      {page.isLoading && <KitLoading />}
      <ErrorText error={page.error} />
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
        <span className="text-small font-semibold">Send to</span>
        <FilterPills
          label="Send to"
          options={[["", data.wards.length === 1 ? data.wards[0].name : "All my wards"], ...(data.wards.length > 1 ? data.wards.map((w) => [w.id, w.name]) : [])]}
          value={form.wards.length ? form.wards : [""]}
          onChange={(id) => (id ? toggle(id) : change({ wards: [] }))}
        />
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

      <MessageField value={form.body} onChange={(body) => change({ body })} text={text} />

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

const wardsOf = (m) => (m.ward_names.length ? m.ward_names.join(", ") : "all wards");

function Drafts({ data }) {
  return (
    <DraftList
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
  if (log.isLoading) return <KitLoading />;
  if (log.error) return <ErrorText error={log.error} />;
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
