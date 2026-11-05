import { useMobilizers, useStrategy } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { formatNumber as fmt } from "@/lib/format";
import { holderOf, statusOf } from "./helpers";
import StrategyNotes from "./StrategyNotes";
import WsHeader, { KitError, KitLoading } from "./WsHeader";

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
    ["Mobilizers", `${staffed} / ${units}`, `${quiet} ${noun}${quiet === 1 ? "" : "s"} with no event yet`],
  ];
  return (
    <section aria-label="Win number" className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-6 rounded-card bg-ink p-7 text-on-dark">
      {tiles.map(([label, value, note, tone]) => (
        <div key={label} className="flex flex-col gap-1.5">
          <span className="text-ui font-semibold text-on-dark-muted">{label}</span>
          <span className={`font-display text-[36px] leading-none font-extrabold ${tone || ""}`}>{value}</span>
          <span className="text-small text-on-dark-muted">{note}</span>
        </div>
      ))}
    </section>
  );
}

function Targets({ units, mobilizers, noun }) {
  const rows = [...units].sort((a, b) => b.gap - a.gap);
  const title = noun === "centre" ? "Centre targets" : "Ward targets";
  return (
    <Card variant="outline" className="min-w-0 flex-[3_1_460px] gap-3" role="region" aria-labelledby="targets-h">
      <h2 id="targets-h" className="text-card-title font-bold">{title}</h2>
      <Table minWidth={620}>
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
  const noun = campaign.operational_grain === "centre" ? "centre" : "ward";
  const actions = (
    <>
      {role !== "candidate" && <Button shape="rounded" variant="quiet" onClick={() => onModal({ type: "event" })}>Schedule event</Button>}
      {ADDS_MOBILIZERS.includes(role) && <Button shape="rounded" onClick={() => onModal({ type: "mobilizer" })}>Add mobilizer</Button>}
    </>
  );
  return (
    <>
      <WsHeader context="Plan" title="Overview" sub={role === "candidate" ? "Where the campaign stands today." : "Your command view of the seat."} actions={actions} />
      {strategy.isLoading && <KitLoading />}
      {strategy.error && <KitError error={strategy.error} />}
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
