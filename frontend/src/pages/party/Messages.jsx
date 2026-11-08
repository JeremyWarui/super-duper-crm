// The party office's texts to members and volunteers: the Comms Officer drafts, the Party Super
// Admin approves and sends, and only people whose consent covers SMS receive one.
import { useState } from "react";
import { useDeclinePartyMessage, useDraftPartyMessage, usePartyMessageReach, usePartyMessages, useSendPartyMessage } from "@/api/hooks";
import PlaceCascade from "@/components/PlaceCascade";
import { DraftList, MessageField, SentList } from "@/components/SmsParts";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorText } from "@/components/ui/error-text";
import { LoadingText } from "@/components/ui/loading-text";
import { FilterPills } from "@/components/ui/tabs";
import { plural } from "@/lib/format";
import { FOOTER } from "@/lib/sms";

const AUDIENCES = [
  ["members", "Members", "members who ticked SMS updates when they joined"],
  ["volunteers", "Volunteers", "active volunteers who chose SMS as their contact"],
];
const WHO = Object.fromEntries(AUDIENCES.map(([k, l]) => [k, l.toLowerCase()]));

export default function Messages() {
  const page = usePartyMessages();
  if (page.isLoading) return <LoadingText />;
  if (page.error) return <ErrorText error={page.error} />;
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

function Compose() {
  const [audience, setAudience] = useState("members");
  const [where, setWhere] = useState({ county: "", constituency: "", ward: "" });
  const [body, setBody] = useState("");
  const [done, setDone] = useState("");
  const place = { audience, county: where.county || null, constituency: where.constituency || null, ward: where.ward || null };
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
        <span className="text-small font-semibold">Audience</span>
        <FilterPills label="Audience" options={AUDIENCES} value={audience} onChange={touch(setAudience)} />
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <PlaceCascade labelled place={where} onChange={touch(setWhere)} blank={(lv) => (lv === "county" ? "All counties" : "All")} />
      </div>
      <p className="text-small text-muted-foreground" aria-live="polite">
        {count === null ? "Counting…" : (
          <>
            <strong className="text-ink">{plural(count, "recipient")}</strong>: {AUDIENCES.find(([k]) => k === audience)[2]}
            {reach.data.opted_out > 0 && `. ${plural(reach.data.opted_out, "number")} that replied STOP ${reach.data.opted_out === 1 ? "is" : "are"} left out`}.
          </>
        )}
      </p>
      <MessageField value={body} onChange={touch(setBody)} text={text} />
      <ErrorText error={save.error} />
      {done && <p role="status" className="font-semibold text-ok-foreground">{done}</p>}
      <Button shape="rounded" className="self-start" disabled={!ready}
        onClick={() => save.mutate({ ...place, body: body.trim() }, { onSuccess: () => { setBody(""); setDone("Saved. The Party Super Admin approves it before it is sent."); } })}>
        {save.isPending ? "Saving…" : "Send for approval"}
      </Button>
      <p className="text-small text-muted-foreground">Nothing is sent until the Party Super Admin approves it, and never by whoever drafted it.</p>
    </Card>
  );
}

const aboutDraft = (m) => `${WHO[m.audience]}, ${m.place} · ${plural(m.targeted, "recipient")} when drafted`;

function Drafts({ data }) {
  return (
    <DraftList
      drafts={data.messages.filter((m) => m.status === "draft")}
      about={aboutDraft}
      decide={(m) => (!data.can_send ? false : m.mine ? "Someone else approves your own draft." : true)}
      approve={useSendPartyMessage()}
      decline={useDeclinePartyMessage()}
    />
  );
}

function History({ data }) {
  return <SentList messages={data.messages.filter((m) => m.status !== "draft")} title="Recent sends" about={(m) => `${WHO[m.audience]}, ${m.place}`} sentBy="approved by" />;
}
