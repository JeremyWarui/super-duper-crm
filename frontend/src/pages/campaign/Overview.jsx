import { useMobilizers, useStrategy } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { formatNumber as fmt, plural } from "@/lib/format";
import { holderOf, statusOf, unitOf } from "./helpers";
import StrategyNotes from "./StrategyNotes";
import { ErrorText } from "@/components/ui/error-text";
import { SlottedHeader } from "@/components/layout/AppPage";
import { LoadingText } from "@/components/ui/loading-text";
import { FigureBand } from "@/components/ui/stat-tiles";

const TONE = { good: "ok", warn: "warn", bad: "bad" };
const ADDS_MOBILIZERS = ["candidate", "manager", "coordinator"];

function Hero({ s, noun }) {
  const units = s.units.length;
  const short = s.units.filter((u) => u.gap > 0).length;
  const staffed = s.units.filter((u) => u.has_mobilizer).length;
  const quiet = s.units.filter((u) => u.events === 0).length;
  const tiles = [
    ["Win number", fmt(s.win_number), `Half the projected votes, plus one, in each ${noun}`, "text-accent"],
    ["Votes committed", fmt(s.committed), `${s.progress_pct}% of the win number`],
    ["Gap to close", fmt(Math.max(s.win_number - s.committed, 0)), `Across ${short} of ${units} ${noun}s`],
    ["Mobilizers", `${staffed} / ${units}`, `${plural(quiet, noun)} with no event yet`],
  ];
  return (
    <FigureBand label="Win number" figures={tiles} />
  );
}

function Targets({ units, mobilizers, noun }) {
  const rows = [...units].sort((a, b) => b.gap - a.gap);
  const title = noun === "centre" ? "Centre targets" : "Ward targets";
  return (
    <Card variant="outline" className="min-w-0 flex-[3_1_460px] gap-3" role="region" aria-labelledby="targets-h">
      <CardTitle id="targets-h">{title}</CardTitle>
      <Table stack minWidth={620}>
        <THead><TR>
          <TH>{noun === "centre" ? "Centre" : "Ward"}</TH><TH align="right">Win number</TH><TH align="right">Committed</TH>
          <TH align="right">Events</TH><TH>Mobilizer</TH><TH>Status</TH>
        </TR></THead>
        <TBody>{rows.map((u) => {
          const st = statusOf(u.progress);
          const holder = holderOf(mobilizers, u);
          return (
            <TR key={u.unit}>
              <TD className="font-semibold">{u.unit}</TD>
              <TD numeric>{fmt(u.needed)}</TD>
              <TD numeric>{fmt(u.committed)} <span className="text-small text-muted-foreground">· {Math.round(u.progress * 100)}%</span></TD>
              <TD numeric className={u.events === 0 ? "font-semibold text-bad-foreground" : undefined}>{u.events}</TD>
              <TD>{holder ? holder.full_name : <span className="font-semibold text-bad-foreground">None</span>}</TD>
              <TD><Badge tone={TONE[st.tone]}>{st.label}</Badge></TD>
            </TR>
          );
        })}</TBody>
      </Table>
      <p className="text-small text-muted-foreground">Biggest gap first. Assign mobilizers on the {noun === "centre" ? "Centres" : "Wards"} page.</p>
    </Card>
  );
}

// The campaign at a glance: the win number and how far there is to go, every targeted unit, and
// the strategy read.
export default function Overview({ campaign, role, onModal }) {
  const strategy = useStrategy(campaign.id);
  const mobilizers = useMobilizers(campaign.id);
  const { noun } = unitOf(campaign);
  const actions = (
    <>
      {role !== "candidate" && <Button variant="quiet" onClick={() => onModal({ type: "event" })}>Schedule event</Button>}
      {ADDS_MOBILIZERS.includes(role) && <Button onClick={() => onModal({ type: "mobilizer" })}>Add mobilizer</Button>}
    </>
  );
  return (
    <>
      <SlottedHeader context="Plan" title="Overview" sub={role === "candidate" ? "Where the campaign stands today." : "Your command view of the seat."} actions={actions} />
      {strategy.isLoading && <LoadingText />}
      <ErrorText error={strategy.error} />
      {strategy.data && (
        <>
          <Hero s={strategy.data} noun={noun} />
          <div className="flex flex-wrap items-start gap-6">
            <Targets units={strategy.data.units} mobilizers={mobilizers.data || []} noun={noun} />
            <div className="flex min-w-0 flex-[2_1_320px] flex-col gap-6"><StrategyNotes notes={strategy.data.notes} /></div>
          </div>
        </>
      )}
    </>
  );
}
