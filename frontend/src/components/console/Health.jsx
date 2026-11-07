// The console's Health tab: what is running, what is switched on, and the last backups.
import { useState } from "react";
import { useBackups, useHealth, useTestSend, useTestService } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";

const GB = 1024 ** 3;
const size = (bytes) => (bytes == null ? "unknown" : bytes >= GB ? `${(bytes / GB).toFixed(1)} GB` : `${(bytes / 1024 ** 2).toFixed(1)} MB`);
const when = (iso) => (iso ? new Date(iso).toLocaleString() : "never");

function Row({ label, children }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line-soft py-2.5 first:border-t-0">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-semibold">{children}</span>
    </div>
  );
}

function TestSend({ kind, label, note }) {
  const send = useTestSend();
  const [phone, setPhone] = useState("");
  return (
    <form className="flex flex-col gap-2" onSubmit={(e) => { e.preventDefault(); send.mutate({ kind, phone }); }}>
      <Field label={`${label}: phone number`} hint={note}>
        <Input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} />
      </Field>
      <Button type="submit" shape="rounded" variant="quiet" className="self-start" disabled={phone.trim().length < 3 || send.isPending}>
        {send.isPending ? "Sending…" : label}
      </Button>
      {send.data && <p role="status" className="text-ui font-semibold text-primary">{send.data.message}</p>}
      {send.error && <p role="alert" className="text-ui font-semibold text-destructive">{send.error.message}</p>}
    </form>
  );
}

/** A check that Google answers, once its keys are set. */
function SignIn({ google }) {
  const check = useTestService();
  return (
    <Card variant="outline" className="gap-3" role="region" aria-label="Sign-in">
      <h2 className="text-card-title font-bold">Sign-in</h2>
      <p className="text-ui text-muted-foreground">Everyone signs in with email and password; Google sign-in shows beside it once its keys are set.</p>
      <div className="flex flex-col gap-2">
        <Button type="button" shape="rounded" variant="quiet" className="self-start" disabled={!google || check.isPending} onClick={() => check.mutate("google")}>
          {check.isPending ? "Checking…" : "Check Google sign-in"}
        </Button>
        {!google && <p className="text-small text-muted-foreground">Google sign-in is off. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to <code>.env</code> and restart.</p>}
        {check.data && <p role="status" className="text-ui font-semibold text-primary">{check.data.message}</p>}
        {check.error && <p role="alert" className="text-ui font-semibold text-destructive">{check.error.message}</p>}
      </div>
    </Card>
  );
}

export default function Health() {
  const { data: h, isLoading, error } = useHealth();
  const backups = useBackups().data || [];
  if (isLoading) return <p className="kit text-muted-foreground">Checking…</p>;
  if (error) return <p role="alert" className="kit font-semibold text-destructive">{error.message}</p>;
  const last = h.last_backup;
  return (
    <div className="kit flex flex-col gap-4">
      <Card variant="outline" className="gap-1" role="region" aria-label="Installation">
        <h2 className="text-card-title font-bold">Installation</h2>
        <Row label="Version">{h.version}</Row>
        <Row label="Database">{h.database.reachable ? <Badge tone="ok">Reachable</Badge> : <Badge tone="bad">{h.database.detail || "Unreachable"}</Badge>}</Row>
        {h.database.size_bytes != null && <Row label="Database size">{size(h.database.size_bytes)}</Row>}
        <Row label="Migration">
          {h.migration.up_to_date
            ? <Badge tone="ok">Up to date ({h.migration.current})</Badge>
            : <Badge tone="warn">At {h.migration.current || "unknown"}, latest {h.migration.head || "unknown"}: run alembic upgrade head</Badge>}
        </Row>
        <Row label="Organisation type"><span className="capitalize">{h.organisation_type || "not set up"}</span></Row>
        {h.disks.map((d) => <Row key={d.label} label={`Free space, ${d.label.toLowerCase()}`}>{size(d.free_bytes)} of {size(d.total_bytes)}</Row>)}
      </Card>
      <Card variant="outline" className="gap-1" role="region" aria-label="Outside services">
        <h2 className="text-card-title font-bold">Outside services</h2>
        <p className="text-ui text-muted-foreground">Set in the server's <code>.env</code>; anything not configured runs in practice mode and sends nothing.</p>
        {h.services.map((s) => (
          <Row key={s.key} label={s.label}>{s.configured ? <Badge tone="ok">Configured ({s.mode})</Badge> : <Badge tone="stone">Not configured</Badge>}</Row>
        ))}
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <TestSend kind="sms" label="Send a test SMS" note="Sends one short text." />
          <TestSend kind="payout" label="Make a practice payout" note="KES 1 in practice mode; refused where payouts are live." />
        </div>
      </Card>
      <SignIn google={h.services.some((s) => s.key === "google" && s.configured)} />
      <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Backups">
        <h2 className="text-card-title font-bold">Backups</h2>
        <p className="text-ui">
          Last backup: <strong>{last ? `${when(last.at)} (${last.status})` : "never"}</strong>.{" "}
          <span className="text-muted-foreground">Run <code>campaign-crm backup</code> on the server every night; it keeps 14 daily and 8 weekly archives.</span>
        </p>
        {backups.length > 0 && (
          <Table stack minWidth={560}>
            <THead><TR><TH>When</TH><TH>Status</TH><TH>Size</TH><TH>Archive</TH></TR></THead>
            <TBody>
              {backups.map((b) => (
                <TR key={b.id}>
                  <TD>{when(b.finished_at || b.created_at)}</TD>
                  <TD><Badge tone={b.status === "ok" ? "ok" : b.status === "failed" ? "bad" : "warn"}>{b.status}</Badge></TD>
                  <TD className="tabular-nums">{size(b.size)}</TD>
                  <TD className="break-all text-muted-foreground">{b.status === "failed" ? b.detail : b.path}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </Card>
    </div>
  );
}
