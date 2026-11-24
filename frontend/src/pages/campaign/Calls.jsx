// Online calls: start one for the whole campaign, a ward or (in an MCA race) a centre, share its
// link, and see who came.
import { useState } from "react";
import { Link } from "react-router-dom";
import { useCalls, useStartCall } from "@/api/hooks";
import { SlottedHeader } from "@/components/layout/AppPage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { ErrorText } from "@/components/ui/error-text";
import { Field, Input, NativeSelect } from "@/components/ui/input";
import { placeOf, UnitSelect, useUnitOptions } from "./UnitSelect";
import { LoadingText } from "@/components/ui/loading-text";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { formatDateTime } from "@/lib/format";
import { LinkCard } from "./ShareLink";

export default function Calls({ campaign, role }) {
  return (
    <>
      <SlottedHeader context="Reach out" title="Calls" sub="Audio or video calls with the team. Everyone invited gets an alert on the phone where they turned alerts on." />
      <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <StartCall campaign={campaign} wardOnly={role === "coordinator"} />
        <CallList campaign={campaign} />
      </div>
    </>
  );
}

function StartCall({ campaign, wardOnly }) {
  const options = useUnitOptions(campaign);
  const [form, setForm] = useState({ title: "", mode: "video", unit: "" });
  const start = useStartCall(campaign.id);
  const started = start.data;
  const link = started ? `${window.location.origin}${started.join_path}` : "";
  const submit = (e) => {
    e.preventDefault();
    start.mutate({ title: form.title.trim(), mode: form.mode, ...placeOf(options, form.unit) });
  };
  return (
    <Card variant="outline" className="min-w-0 content-start gap-4" role="region" aria-labelledby="start-call-h">
      <CardTitle id="start-call-h">Start call</CardTitle>
      <form className="flex flex-col gap-3" onSubmit={submit}>
        <Field label="Title"><Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Ward check-in" /></Field>
        <Field label="Call type">
          <NativeSelect value={form.mode} onChange={(e) => setForm({ ...form, mode: e.target.value })}>
            <option value="video">Video</option>
            <option value="audio">Audio only (uses less data)</option>
          </NativeSelect>
        </Field>
        <Field label="Invite">
          <UnitSelect campaign={campaign} options={options} value={form.unit} onChange={(unit) => setForm({ ...form, unit })} wholeCampaign={!wardOnly} />
        </Field>
        <Button type="submit" className="self-start" loading={start.isPending} disabled={start.isPending || !form.title.trim() || (wardOnly && !form.unit)}>Start call</Button>
      </form>
      <ErrorText error={start.error} />
      {started && (
        <div className="grid gap-3 border-t border-line-soft pt-3">
          <p role="status" className="font-semibold">
            {started.alerted ? `Alert sent to ${started.alerted} ${started.alerted === 1 ? "phone" : "phones"}.` : "Nobody invited has call alerts on yet; share the link."}
          </p>
          <LinkCard url={link} qrTitle={`Join ${started.meeting.title}`} />
          <Button asChild className="self-start"><Link to={started.join_path}>Join now</Link></Button>
        </div>
      )}
    </Card>
  );
}

function CallList({ campaign }) {
  const calls = useCalls(campaign.id);
  return (
    <Card variant="outline" className="min-w-0 content-start gap-3" role="region" aria-labelledby="calls-h">
      <CardTitle id="calls-h">Recent calls</CardTitle>
      {calls.isLoading && <LoadingText />}
      <ErrorText error={calls.error} />
      {calls.data?.length === 0 && <p className="text-ui text-muted-foreground">No calls yet.</p>}
      {calls.data?.length > 0 && (
        <Table stack minWidth={520}>
          <THead><TR><TH>Call</TH><TH>Started</TH><TH align="right">Minutes</TH><TH>Who came</TH></TR></THead>
          <TBody>
            {calls.data.map(({ meeting, host, unit, minutes, attendance }) => (
              <TR key={meeting.id}>
                <TD>
                  <div className="font-semibold">{meeting.title}</div>
                  <div className="flex flex-wrap items-center gap-2 text-small text-muted-foreground">
                    <Badge tone={meeting.status === "live" ? "ok" : "stone"}>{meeting.status === "live" ? "Live" : "Ended"}</Badge>
                    {meeting.mode === "audio" ? "Audio" : "Video"} · {unit} · {host}
                  </div>
                  {meeting.status === "live" && <Link className="text-small font-bold" to={`/meet/${meeting.id}`}>Join</Link>}
                </TD>
                <TD>{formatDateTime(meeting.started_at)}</TD>
                <TD numeric>{minutes}</TD>
                <TD>{attendance.length ? [...new Set(attendance.map((a) => a.name))].join(", ") : "Nobody joined"}</TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
    </Card>
  );
}
