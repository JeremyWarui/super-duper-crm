// The team link mobilizers and agents sign up through, and the queue of sign-ups the candidate,
// manager and coordinators (in their area) approve or reject.
import { useState } from "react";
import { useDecideRegistration, useRegistrations, useReplaceTeamLink, useTeamLink } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ReasonForm } from "@/components/ui/confirm";
import { Card, CardTitle } from "@/components/ui/card";
import { EmptyRow, Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { FilterPills } from "@/components/ui/tabs";
import { formatDate, linkTo } from "../../lib/format";
import { ErrorText } from "@/components/ui/error-text";
import { SlottedHeader } from "@/components/layout/AppPage";
import { LoadingText } from "@/components/ui/loading-text";

const VIEWS = { Waiting: "pending", Approved: "approved", "Not approved": "rejected" };
import { ROLE_LABEL } from "@/lib/labels";
import { isLead } from "./helpers";
import { LinkCard } from "./ShareLink";
import { StatusText } from "@/components/ui/notice";

function TeamLinkCard({ campaign, role }) {
  const link = useTeamLink(campaign.id);
  const replace = useReplaceTeamLink();
  const url = link.data ? linkTo(`/team/${link.data.code}`) : "";
  return (
    <Card variant="outline" className="min-w-0 flex-[1_1_360px] gap-4" role="region" aria-label="Team link">
      <div className="flex flex-col gap-1">
        <CardTitle>Team sign-up link</CardTitle>
        <p className="text-ui text-muted-foreground">Share it with people who want to be mobilizers or agents. Every sign-up waits for a decision here.</p>
      </div>
      <ErrorText error={link.error} />
      {link.data && (
        <LinkCard url={url} qrTitle="Team sign-up QR code" replacing={replace.isPending}
          onReplace={isLead(role) ? () => replace.mutate(campaign.id) : undefined}
          note="Replacing it stops the old link and QR code from working." />
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
        <ReasonForm label={`Reason for not approving ${row.full_name}`} placeholder="Why not" value={reason} onChange={setReason} min={3}
          yes="Reject with this reason" no="Back" busy={decide.isPending} onYes={() => send("reject")} onNo={() => setRejecting(false)} />
        <ErrorText error={decide.error} className="text-small" />
      </div>
    );
  }
  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex justify-end gap-2">
        <Button shape="rounded" size="sm" disabled={decide.isPending} onClick={() => send("approve")} aria-label={`Approve ${row.full_name}`}>Approve</Button>
        <Button shape="rounded" size="sm" variant="quiet" onClick={() => setRejecting(true)} aria-label={`Reject ${row.full_name}`}>Reject</Button>
      </div>
      <ErrorText error={decide.error} className="text-small" />
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
      <SlottedHeader context="People" title="Sign-ups" sub="Mobilizers and agents who signed up on the team link." />
      <TeamLinkCard campaign={campaign} role={role} />
      <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Sign-ups">
        <FilterPills label="Status" options={Object.keys(VIEWS)} value={view} onChange={(v) => { setView(v); setDone(""); }} />
        {done && <StatusText boxed className="p-3 text-ui">{done}</StatusText>}
        {rows.isLoading && <LoadingText />}
        <ErrorText error={rows.error} />
        {rows.data && (
          <Table stack minWidth={760}>
            <THead><TR>
              <TH>Name</TH><TH>Role</TH><TH>Ward or centre</TH><TH>Contact</TH>{ids && <TH>ID number</TH>}<TH>Signed up</TH>
              {waiting ? <TH srOnly>Decision</TH> : <TH>{view === "Not approved" ? "Reason" : ""}</TH>}
            </TR></THead>
            <TBody>
              {list.map((r) => (
                <TR key={r.id}>
                  <TD className="font-semibold">{r.full_name}</TD>
                  <TD><Badge tone={r.role === "agent" ? "info" : "tint"}>{ROLE_LABEL[r.role]}</Badge></TD>
                  <TD>{r.centre_name ? <><div>{r.centre_name}</div><div className="text-small text-muted-foreground">{r.ward_name}</div></> : r.ward_name}</TD>
                  <TD><div className="tabular-nums">{r.phone}</div><div className="text-small text-muted-foreground">{r.email}</div></TD>
                  {ids && <TD className="tabular-nums">{r.id_number || "None"}</TD>}
                  <TD className="text-muted-foreground">{formatDate(r.created_at)}</TD>
                  <TD align="right" className="relative">{waiting ? <Decision campaign={campaign} row={r} onDone={(d, row, data) => setDone(outcome(d, row, data))} /> : <span className="text-small text-muted-foreground">{r.reason}</span>}</TD>
                </TR>
              ))}
              {list.length === 0 && <EmptyRow>{waiting ? "Nobody is waiting for a decision." : "None yet."}</EmptyRow>}
            </TBody>
          </Table>
        )}
      </Card>
    </>
  );
}
