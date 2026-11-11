// Polling agents: how far each has come before polling day, and which registration centres still
// have nobody.
import { exportAgents, useAgentCoverage, useAgents, useUpdateAgent } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Input, NativeSelect } from "@/components/ui/input";
import { EmptyRow, Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { formatNumber as fmt } from "@/lib/format";
import { ErrorText } from "@/components/ui/error-text";
import { StatTiles } from "@/components/ui/stat-tiles";
import { SlottedHeader } from "@/components/layout/AppPage";
import { LoadingText } from "@/components/ui/loading-text";

import { AGENT_STEPS } from "@/lib/labels";
import { isLead } from "./helpers";
import CoverageCard from "./CoverageCard";

function Tiles({ agents, coverage }) {
  const ready = agents.filter((a) => a.status === "ready").length;
  const tiles = [
    ["Agents", fmt(agents.length), "signed up and approved"],
    ["Ready", fmt(ready), "vetted, trained and ready"],
    ["Centres covered", coverage ? `${fmt(coverage.covered)} / ${fmt(coverage.centres)}` : "…", "with at least one agent"],
  ];
  return (
    <StatTiles tiles={tiles} />
  );
}

export default function Agents({ campaign, role, onModal }) {
  const agents = useAgents(campaign.id);
  const coverage = useAgentCoverage(campaign.id);
  const update = useUpdateAgent();
  const rows = agents.data || [];
  const ids = rows.some((a) => a.id_number);
  const action = isLead(role) ? <Button shape="rounded" variant="quiet" onClick={() => exportAgents(campaign.id)}>Export for letters</Button> : null;
  return (
    <>
      <SlottedHeader context="Field" title="Agents" sub="Polling agents, readied for one registration centre each before polling day." actions={action} />
      {agents.isLoading && <LoadingText />}
      <ErrorText error={agents.error} />
      {agents.data && (
        <>
          <Tiles agents={rows} coverage={coverage.data} />
          {coverage.data && (
            <CoverageCard title="Centres with no agent" count={`${fmt(coverage.data.centres - coverage.data.covered)} of ${fmt(coverage.data.centres)}`}
              gaps={coverage.data.uncovered.map((c) => ({ key: c.id, label: c.name, detail: c.ward_name }))} more={coverage.data.more_uncovered} done="Every centre has an agent." />
          )}
          <Card variant="outline" className="min-w-0 gap-3">
            <CardTitle>Everyone</CardTitle>
            <ErrorText error={update.error} />
            <Table stack minWidth={720}>
              <THead><TR><TH>Agent</TH><TH>Centre</TH>{ids && <TH>ID number</TH>}<TH>Status</TH><TH>Training date</TH><TH srOnly className="relative">Assign</TH></TR></THead>
              <TBody>
                {rows.map((a) => (
                  <TR key={a.id}>
                    <TD><div className="font-semibold">{a.full_name}</div><div className="text-small text-muted-foreground tabular-nums">{a.phone}</div></TD>
                    <TD>{a.centre_name ? <><div>{a.centre_name}</div><div className="text-small text-muted-foreground">{a.ward_name}</div></> : <span className="font-semibold text-bad-foreground">No centre</span>}</TD>
                    {ids && <TD className="tabular-nums">{a.id_number || "None"}</TD>}
                    <TD>
                      <NativeSelect aria-label={`Status of ${a.full_name}`} value={a.status} onChange={(e) => update.mutate({ id: a.id, status: e.target.value })}>
                        {AGENT_STEPS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                      </NativeSelect>
                    </TD>
                    <TD>
                      <Input type="date" aria-label={`Training date of ${a.full_name}`} value={a.training_date || ""} onChange={(e) => update.mutate({ id: a.id, training_date: e.target.value || null })} />
                    </TD>
                    <TD align="right"><Button shape="rounded" size="sm" variant="quiet" onClick={() => onModal({ type: "assign-work", member: { role: "agent", id: a.id } })} aria-label={`Assign work to ${a.full_name}`}>Assign work</Button></TD>
                  </TR>
                ))}
                {rows.length === 0 && <EmptyRow>No agents yet. Share the team link from Sign-ups.</EmptyRow>}
              </TBody>
            </Table>
          </Card>
        </>
      )}
    </>
  );
}
