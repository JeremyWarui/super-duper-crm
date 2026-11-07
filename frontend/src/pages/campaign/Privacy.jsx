// Personal data (Candidate, Manager): requests from people about their data, erasing the sign-ups
// of mobilizers and agents who left, and, for the Candidate, closing the campaign after the election.
import { useState } from "react";
import { useCloseCampaign, useCloseState, useErase, useEraseSupporters, useLeftTeam, useSetRetention } from "@/api/hooks";
import DataRequests from "@/components/DataRequests";
import EraseButton from "@/components/EraseButton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { formatDate, formatNumber as fmt } from "@/lib/format";
import WsHeader, { KitLoading } from "./WsHeader";
import { ErrorText } from "@/components/ui/error-text";

const ROLE = { mobilizer: "Mobilizer", agent: "Agent" };

function LeftTeam({ campaign }) {
  const { data, isLoading, error } = useLeftTeam(campaign.id);
  const erase = useErase(campaign.id, "registrations");
  return (
    <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="People who left the team">
      <h2 className="text-[18px] font-bold">People who left the team</h2>
      <p className="text-small text-muted-foreground">
        Mobilizers and agents who were turned down or are off the team. Erasing clears their name, phone, email and ID number.
      </p>
      {isLoading && <KitLoading />}
      <ErrorText error={error} />
      <ErrorText error={erase.error} />
      {data && (
        <Table stack minWidth={520}>
          <THead><TR><TH>Name</TH><TH>Signed up as</TH><TH>Outcome</TH><TH>Signed up</TH><TH><span className="sr-only">Erase</span></TH></TR></THead>
          <TBody>
            {data.map((r) => (
              <TR key={r.id}>
                <TD className="font-semibold">{r.full_name}</TD>
                <TD>{ROLE[r.role] || r.role}</TD>
                <TD>{r.status === "rejected" ? "Turned down" : "Left the team"}</TD>
                <TD className="text-muted-foreground">{formatDate(r.created_at)}</TD>
                <TD align="right"><EraseButton name={r.full_name} pending={erase.isPending} onErase={(done) => erase.mutate(r.id, { onSuccess: done })} /></TD>
              </TR>
            ))}
            {data.length === 0 && <TR><TD colSpan={5} className="text-muted-foreground">Nobody to erase.</TD></TR>}
          </TBody>
        </Table>
      )}
    </Card>
  );
}

function Retention({ campaign, state }) {
  const [months, setMonths] = useState(String(state.retention_months));
  const save = useSetRetention(campaign.id);
  return (
    <div className="flex flex-wrap items-end gap-2">
      <Field label="Keep supporter details after closing (months)" className="w-[260px]">
        <Input type="number" min={1} max={60} value={months} onChange={(e) => setMonths(e.target.value)} />
      </Field>
      <Button size="sm" shape="rounded" variant="quiet" disabled={save.isPending || Number(months) === state.retention_months} onClick={() => save.mutate(Number(months))}>Save</Button>
      <ErrorText error={save.error} className="w-full text-small" />
    </div>
  );
}

function Closing({ campaign, role }) {
  const { data: state, isLoading, error } = useCloseState(campaign.id);
  const close = useCloseCampaign(campaign.id);
  const eraseAll = useEraseSupporters(campaign.id);
  const [asking, setAsking] = useState(false);
  const candidate = role === "candidate";
  if (isLoading) return <KitLoading />;
  if (error) return <ErrorText error={error} />;
  const due = state.erase_from && new Date(state.erase_from) <= new Date();
  return (
    <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="After the election">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-[18px] font-bold">After the election</h2>
        {state.closed_at ? <Badge tone="stone">Closed {formatDate(state.closed_at)}</Badge> : <Badge tone="ok">Open</Badge>}
      </div>
      {!state.closed_at ? (
        <>
          <p className="text-small text-muted-foreground">
            Closing makes this workspace read-only for everyone and stops new sign-ups. Supporter details are kept for {state.retention_months} months after that, then the candidate can erase them. Nothing is erased on its own.
          </p>
          {candidate ? (
            <>
              <Retention key={state.retention_months} campaign={campaign} state={state} />
              {!asking ? (
                <Button shape="rounded" variant="danger" className="self-start" onClick={() => setAsking(true)}>Close the campaign</Button>
              ) : (
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-ui font-semibold">Close for good? This cannot be undone.</span>
                  <Button shape="rounded" variant="danger" disabled={close.isPending} onClick={() => close.mutate(undefined, { onSuccess: () => setAsking(false) })}>Yes, close it</Button>
                  <Button shape="rounded" variant="ghost" onClick={() => setAsking(false)}>Cancel</Button>
                </div>
              )}
              <ErrorText error={close.error} />
            </>
          ) : <p className="text-small text-muted-foreground">Only the candidate closes the campaign.</p>}
        </>
      ) : state.supporters_erased_at ? (
        <p className="text-ui">Supporter details were erased on {formatDate(state.supporters_erased_at)}. {fmt(state.supporters)} supporters stay counted.</p>
      ) : (
        <>
          <p className="text-ui">
            {fmt(state.supporters - state.erased)} of {fmt(state.supporters)} supporters still have their details. They can be erased from {formatDate(state.erase_from)}.
          </p>
          {candidate && due ? (
            <EraseButton name="every supporter's details" pending={eraseAll.isPending} onErase={(done) => eraseAll.mutate(undefined, { onSuccess: done })} />
          ) : null}
          <ErrorText error={eraseAll.error} />
        </>
      )}
    </Card>
  );
}

export default function Privacy({ campaign, role }) {
  return (
    <>
      <WsHeader context="People" title="Personal data" sub="Answer requests about people's details, and erase them when asked." />
      <DataRequests campaignId={campaign.id} />
      <LeftTeam campaign={campaign} />
      {campaign.kind !== "party" && <Closing campaign={campaign} role={role} />}
    </>
  );
}
