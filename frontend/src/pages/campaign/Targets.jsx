// The seat's targets (TD-R7, mockup M3): the share the last winner took, the turnout scenarios to
// try, the one the team works to, and each ward's share. Trying a scenario saves nothing; setting
// one is for the candidate or the manager, confirmed, and tells the team.
import { useState } from "react";
import { useRefreshTargets, useSetScenario, useTargetsPreview } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { formatNumber as fmt } from "@/lib/format";
import { ErrorText } from "@/components/ui/error-text";
import { SlottedHeader } from "@/components/layout/AppPage";
import { LoadingText } from "@/components/ui/loading-text";
import { FigureBand } from "@/components/ui/stat-tiles";
import { StatusText } from "@/components/ui/notice";
import { isNational, unitOf } from "./helpers";
import CountyFilter from "./CountyFilter";

const SCENARIO = { low: "Low", expected: "Expected", high: "High" };
const RELIABILITY = { seat: ["Seat data, 2022", "ok"], typical: ["Typical winner", "warn"], proxy: ["Proxy", "warn"] };
const SETTERS = ["candidate", "manager"];
const DAY = 24 * 60 * 60 * 1000;

const progressOf = (supporters, target) => (target ? Math.min(Math.round((supporters / target) * 100), 999) : 0);

export default function Targets({ campaign, role }) {
  const national = isNational(campaign);
  const [place, setPlace] = useState({ county: "", constituency: "" });
  const [trying, setTrying] = useState(null);
  const [confirming, setConfirming] = useState(false);
  const county = national ? place.county || undefined : undefined;
  const view = useTargetsPreview(campaign.id, trying || undefined, county);
  const setScenario = useSetScenario(campaign.id);
  const refresh = useRefreshTargets();
  const { noun } = unitOf(campaign);
  const canSet = SETTERS.includes(role);
  const p = view.data;
  const previewing = p && p.scenario !== p.set_scenario;

  const action = canSet ? (
    <Button loading={refresh.isPending} variant="quiet" disabled={refresh.isPending} onClick={() => refresh.mutate(campaign.id)}
      title="Work every target out again from the latest register and past results; supporters recorded stay.">
      {refresh.isPending ? "Refreshing…" : "Refresh targets"}
    </Button>
  ) : null;
  const pick = (scenario) => { setConfirming(false); setTrying(scenario === p?.set_scenario ? null : scenario); };
  const commit = () => setScenario.mutate(p.scenario, { onSuccess: () => { setConfirming(false); setTrying(null); } });

  return (
    <>
      <SlottedHeader context="Plan" title="Targets"
        sub={p?.valid_votes ? `Based on 2022: the winner took ${fmt(p.winner_votes)} of ${fmt(p.valid_votes)} valid votes (${p.share_pct}%).` : "The share the last winner took, applied to the votes expected."}
        actions={action} />
      {refresh.isSuccess && <StatusText>Refreshed: {fmt(refresh.data.units)} {noun}s, seat target {fmt(refresh.data.win_number)}.</StatusText>}
      {setScenario.isSuccess && <StatusText>The team now works to {SCENARIO[setScenario.data.scenario]} turnout: {fmt(setScenario.data.units_changed)} {noun} targets changed and {fmt(setScenario.data.notified)} people were told.</StatusText>}
      <ErrorText error={refresh.error || setScenario.error} />
      {national && <CountyFilter place={place} onChange={setPlace} />}
      {view.isLoading && <LoadingText />}
      <ErrorText error={view.error} />
      {p && (
        <>
          <Card variant="outline" className="min-w-0 gap-3" role="region" aria-labelledby="turnout-h">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <CardTitle id="turnout-h">Turnout</CardTitle>
              <span className="flex flex-wrap items-center gap-2 text-small">
                <Badge tone={RELIABILITY[p.reliability][1]}>{RELIABILITY[p.reliability][0]}</Badge>
                {p.uses_2017 && <Badge tone="stone">Uses 2017 data, later withdrawn</Badge>}
                <span className="font-semibold">Team is working to: {SCENARIO[p.set_scenario]}</span>
              </span>
            </div>
            <div className="grid max-w-[420px] grid-cols-3 gap-2" role="group" aria-label="Turnout scenario">
              {p.scenarios.map((s) => (
                <Button key={s.scenario} size="sm" variant={s.scenario === p.scenario ? "primary" : "outline"} aria-pressed={s.scenario === p.scenario} onClick={() => pick(s.scenario)}
                  className="h-auto min-h-11 flex-col gap-0 px-2 py-1.5 leading-tight">
                  <span>{SCENARIO[s.scenario]}</span>
                  <span className="text-small font-semibold tabular-nums opacity-85">{s.turnout_pct}%</span>
                </Button>
              ))}
            </div>
            {previewing && !confirming && (
              <div role="status" className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-warn/15 px-4 py-3">
                <span className="text-ui">Previewing <strong>{SCENARIO[p.scenario]}</strong> turnout. Your team is working to {SCENARIO[p.set_scenario]}. Nothing is saved.</span>
                <span className="flex gap-2">
                  <Button size="sm" variant="quiet" onClick={() => setTrying(null)}>Back to set scenario</Button>
                  {canSet && <Button size="sm" onClick={() => setConfirming(true)}>Use this scenario</Button>}
                </span>
              </div>
            )}
            {previewing && confirming && (
              <Confirm p={p} noun={noun} election={campaign.election_date} busy={setScenario.isPending} onCancel={() => setConfirming(false)} onConfirm={commit} />
            )}
          </Card>
          <FigureBand label="Targets" figures={[
            ["Votes to win", fmt(p.seat_target), `${p.share_pct}% of ${fmt(p.scenarios.find((s) => s.scenario === p.scenario).projected)} expected`, "text-accent"],
            ["Supporters", fmt(p.supporters)],
            ["Typical winner", p.typical_pct ? `${p.typical_pct}%` : "–", "2013 to 2022"],
            ["Majority line", fmt(p.majority), p.two_candidate ? "The target never goes below it" : "For reference"],
          ]} />
          {national && !place.county && <p className="text-ui text-muted-foreground">Pick a county to see the targets in its wards.</p>}
          {(!national || place.county) && <Card variant="outline" className="min-w-0 gap-3" role="region" aria-labelledby="units-h">
            <CardTitle id="units-h">Target per {noun}</CardTitle>
            <Table stack minWidth={560}>
              <THead><TR>
                <TH>{noun === "centre" ? "Centre" : "Ward"}</TH><TH align="right">Target</TH>{previewing && <TH align="right">Change</TH>}<TH align="right">Supporters</TH><TH align="right">Progress</TH>
              </TR></THead>
              <TBody>{p.units.map((u) => {
                const change = u.set_target == null ? null : u.target - u.set_target;
                return (
                  <TR key={`${u.ward}-${u.registration_centre || ""}`}>
                    <TD className="font-semibold">{u.name}</TD>
                    <TD numeric className="font-bold">{fmt(u.target)}</TD>
                    {previewing && <TD numeric>{change == null ? "–" : `${change > 0 ? "+" : ""}${fmt(change)}`}</TD>}
                    <TD numeric>{fmt(u.supporters)}</TD>
                    <TD numeric>{progressOf(u.supporters, u.target)}%</TD>
                  </TR>
                );
              })}</TBody>
            </Table>
            <p className="text-small text-muted-foreground">Each {noun} is asked for the same {p.share_pct}%, weighted by its 2022 valid votes. The {noun} targets always add up to the seat target.</p>
          </Card>}
        </>
      )}
    </>
  );
}

function Confirm({ p, noun, election, busy, onCancel, onConfirm }) {
  const changed = p.units_changed;
  const soon = election && new Date(election) - Date.now() < 30 * DAY && new Date(election) >= Date.now() - DAY;
  return (
    <div role="alertdialog" aria-labelledby="confirm-h" className="grid gap-3 rounded-lg border border-line bg-surface p-4">
      <strong id="confirm-h">Set {SCENARIO[p.scenario]} turnout for the whole team?</strong>
      <p className="text-ui">
        Seat target {fmt(p.set_seat_target)} → {fmt(p.seat_target)}. {fmt(changed)} {noun} targets change, and each coordinator and
        mobilizer affected gets a notice. This is recorded in the audit trail.
      </p>
      {soon && <p className="text-ui font-semibold text-bad-foreground">The election is less than 30 days away. Your team has been working to the current targets.</p>}
      <div className="flex flex-wrap gap-2">
        <Button variant="quiet" onClick={onCancel}>Cancel</Button>
        <Button loading={busy} disabled={busy} onClick={onConfirm}>Set for the team</Button>
      </div>
    </div>
  );
}
