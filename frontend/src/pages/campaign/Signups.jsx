// The team link mobilizers and agents sign up through, and the queue of sign-ups the candidate,
// manager and coordinators (in their area) approve or reject.
import { useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { useDecideRegistration, useRegistrations, useReplaceTeamLink, useTeamLink } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { FilterPills } from "@/components/ui/tabs";
import WsHeader, { KitError, KitLoading } from "./WsHeader";

const VIEWS = { Waiting: "pending", Approved: "approved", "Not approved": "rejected" };
const ROLE = { mobilizer: "Mobilizer", agent: "Agent" };
const LINK_WRITERS = ["candidate", "manager"];

function TeamLinkCard({ campaign, role }) {
  const link = useTeamLink(campaign.id);
  const replace = useReplaceTeamLink();
  const [copied, setCopied] = useState(false);
  const url = link.data ? `${window.location.origin}/team/${link.data.code}` : "";
  return (
    <Card variant="outline" className="min-w-0 flex-[1_1_360px] gap-4" role="region" aria-label="Team link">
      <div className="flex flex-col gap-1">
        <h2 className="text-card-title font-bold">Team sign-up link</h2>
        <p className="text-ui text-muted-foreground">Share it with people who want to be mobilizers or agents. Every sign-up waits for a decision here.</p>
      </div>
      {link.error && <KitError error={link.error} />}
      {link.data && (
        <div className="flex flex-wrap items-start gap-5">
          <div className="rounded-xl border border-line bg-white p-3"><QRCodeSVG value={url} size={132} title="Team sign-up QR code" /></div>
          <div className="flex min-w-0 flex-[1_1_220px] flex-col gap-3">
            <a href={url} className="break-all font-semibold">{url}</a>
            <div className="flex flex-wrap gap-2">
              <Button shape="rounded" variant="quiet" size="sm" onClick={() => navigator.clipboard?.writeText(url).then(() => setCopied(true), () => setCopied(false))}>{copied ? "Copied" : "Copy link"}</Button>
              {LINK_WRITERS.includes(role) && <Button shape="rounded" variant="ghost" size="sm" disabled={replace.isPending} onClick={() => replace.mutate(campaign.id)}>Replace link</Button>}
            </div>
            {LINK_WRITERS.includes(role) && <p className="text-small text-muted-foreground">Replacing it stops the old link and QR code from working.</p>}
          </div>
        </div>
      )}
    </Card>
  );
}

function Decision({ campaign, row, onDone }) {
  const decide = useDecideRegistration();
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const send = (decision) => decide.mutate({ campaign: campaign.id, id: row.id, decision, reason }, { onSuccess: (data) => onDone(decision, row, data) });
  if (rejecting) {
    return (
      <div className="flex flex-col gap-2">
        <Input aria-label={`Reason for not approving ${row.full_name}`} placeholder="Why not" value={reason} onChange={(e) => setReason(e.target.value)} />
        <div className="flex gap-2">
          <Button shape="rounded" size="sm" variant="danger" disabled={reason.trim().length < 3 || decide.isPending} onClick={() => send("reject")}>Reject with this reason</Button>
          <Button shape="rounded" size="sm" variant="ghost" onClick={() => setRejecting(false)}>Back</Button>
        </div>
        {decide.error && <p role="alert" className="text-small font-semibold text-destructive">{decide.error.message}</p>}
      </div>
    );
  }
  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex justify-end gap-2">
        <Button shape="rounded" size="sm" disabled={decide.isPending} onClick={() => send("approve")} aria-label={`Approve ${row.full_name}`}>Approve</Button>
        <Button shape="rounded" size="sm" variant="quiet" onClick={() => setRejecting(true)} aria-label={`Reject ${row.full_name}`}>Reject</Button>
      </div>
      {decide.error && <p role="alert" className="text-small font-semibold text-destructive">{decide.error.message}</p>}
    </div>
  );
}

function outcome(decision, row, data) {
  if (decision === "reject") return `${row.full_name} was not approved; their login is gone.`;
  const sent = data.invite === "email" ? "We emailed them a link to choose their password." : "They have no email, so no link went out.";
  const place = data.placed ? "" : " Their ward or centre already had a mobilizer, so they start with none: place them from the Mobilizers page.";
  return `${row.full_name} is approved. ${sent}${place}`;
}

export default function Signups({ campaign, role }) {
  const [view, setView] = useState("Waiting");
  const [done, setDone] = useState("");
  const rows = useRegistrations(campaign.id, VIEWS[view]);
  const list = rows.data || [];
  const ids = list.some((r) => r.id_number);
  const waiting = view === "Waiting";
  return (
    <>
      <WsHeader context="People" title="Sign-ups" sub="Mobilizers and agents who signed up on the team link." />
      <TeamLinkCard campaign={campaign} role={role} />
      <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Sign-ups">
        <FilterPills label="Status" options={Object.keys(VIEWS)} value={view} onChange={(v) => { setView(v); setDone(""); }} />
        {done && <p role="status" className="rounded-lg bg-primary-tint p-3 text-ui font-semibold text-primary">{done}</p>}
        {rows.isLoading && <KitLoading />}
        {rows.error && <KitError error={rows.error} />}
        {rows.data && (
          <Table minWidth={760}>
            <THead><TR>
              <TH>Name</TH><TH>Role</TH><TH>Ward or centre</TH><TH>Contact</TH>{ids && <TH>ID number</TH>}<TH>Signed up</TH>
              {waiting ? <TH><span className="sr-only">Decision</span></TH> : <TH>{view === "Not approved" ? "Reason" : ""}</TH>}
            </TR></THead>
            <TBody>
              {list.map((r) => (
                <TR key={r.id}>
                  <TD className="font-semibold">{r.full_name}</TD>
                  <TD><Badge tone={r.role === "agent" ? "info" : "tint"}>{ROLE[r.role]}</Badge></TD>
                  <TD>{r.centre_name ? <><div>{r.centre_name}</div><div className="text-small text-muted-foreground">{r.ward_name}</div></> : r.ward_name}</TD>
                  <TD><div className="tabular-nums">{r.phone}</div><div className="text-small text-muted-foreground">{r.email}</div></TD>
                  {ids && <TD className="tabular-nums">{r.id_number || "None"}</TD>}
                  <TD className="text-muted-foreground">{new Date(r.created_at).toLocaleDateString()}</TD>
                  <TD align="right" className="relative">{waiting ? <Decision campaign={campaign} row={r} onDone={(d, row, data) => setDone(outcome(d, row, data))} /> : <span className="text-small text-muted-foreground">{r.reason}</span>}</TD>
                </TR>
              ))}
              {list.length === 0 && <TR><TD colSpan={7} className="text-muted-foreground">{waiting ? "Nobody is waiting for a decision." : "None yet."}</TD></TR>}
            </TBody>
          </Table>
        )}
      </Card>
    </>
  );
}
