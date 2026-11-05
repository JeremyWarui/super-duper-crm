import { useMemo, useState } from "react";
import { useMobilizers, useStrategy } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { FilterPills } from "@/components/ui/tabs";
import { formatNumber as fmt } from "@/lib/format";
import { cn } from "@/lib/utils";
import { assignerFor, holderOf, statusOf } from "./helpers";
import WsHeader, { KitError, KitLoading } from "./WsHeader";

const TONE = { good: "ok", warn: "warn", bad: "bad" };
const BAR = { good: "bg-primary", warn: "bg-accent", bad: "bg-bad-foreground" };
const SORTS = {
  "Biggest gap": (a, b) => b.gap - a.gap,
  "Win number": (a, b) => b.needed - a.needed,
  "Least progress": (a, b) => a.progress - b.progress,
};

function MobilizerCell({ holder, onAssign }) {
  if (holder) {
    return (
      <div className="flex items-center gap-2">
        <span className="font-semibold">{holder.full_name}</span>
        {onAssign && <Button shape="rounded" variant="quiet" size="sm" onClick={() => onAssign(holder)}>Change</Button>}
      </div>
    );
  }
  return onAssign
    ? <Button shape="rounded" variant="quiet" size="sm" onClick={() => onAssign(null)}>Assign</Button>
    : <span className="font-semibold text-bad-foreground">None</span>;
}

// Every targeted unit: its win number, how far it has come, its events and its mobilizer.
export default function Units({ campaign, role, onModal }) {
  const strategy = useStrategy(campaign.id);
  const mobilizers = useMobilizers(campaign.id);
  const assign = assignerFor(role, onModal);
  const [sortKey, setSortKey] = useState("Biggest gap");
  const noun = campaign.operational_grain === "centre" ? "Centre" : "Ward";
  const units = strategy.data?.units;
  const sorted = useMemo(() => [...(units || [])].sort(SORTS[sortKey]), [units, sortKey]);
  return (
    <>
      <WsHeader context="Plan" title={role === "candidate" ? `${noun} performance` : `${noun}s`} sub="Win number, progress and coverage in each one." />
      {strategy.isLoading && <KitLoading />}
      {strategy.error && <KitError error={strategy.error} />}
      {units && (
        <Card variant="outline" className="min-w-0 gap-3" role="region" aria-labelledby="units-h">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="units-h" className="text-card-title font-bold">{noun} targets</h2>
            <FilterPills label="Sort by" options={Object.keys(SORTS)} value={sortKey} onChange={setSortKey} />
          </div>
          <Table minWidth={680}>
            <THead><TR>
              <TH>{noun}</TH><TH align="right">Win number</TH><TH>Progress</TH><TH align="right">Events</TH><TH>Mobilizer</TH>
            </TR></THead>
            <TBody>{sorted.map((u) => {
              const st = statusOf(u.progress);
              return (
                <TR key={u.unit}>
                  <TD><div className="font-semibold">{u.unit}</div><Badge tone={TONE[st.tone]} className="mt-1">{st.label}</Badge></TD>
                  <TD numeric className="font-bold">{fmt(u.needed)}</TD>
                  <TD className="min-w-[180px]">
                    <div className="flex items-center gap-2">
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-line"><div className={cn("h-full rounded-full", BAR[st.tone])} style={{ width: `${Math.min(u.progress * 100, 100)}%` }} /></div>
                      <span className="w-10 text-right text-small font-bold">{Math.round(u.progress * 100)}%</span>
                    </div>
                    <div className="text-small text-muted-foreground">{fmt(u.committed)} committed</div>
                  </TD>
                  <TD numeric className={u.events === 0 ? "font-semibold text-bad-foreground" : undefined}>{u.events}</TD>
                  <TD><MobilizerCell holder={holderOf(mobilizers.data || [], u)} onAssign={assign && ((holder) => assign(u, holder))} /></TD>
                </TR>
              );
            })}</TBody>
          </Table>
        </Card>
      )}
    </>
  );
}
