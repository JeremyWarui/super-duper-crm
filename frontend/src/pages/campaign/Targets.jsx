import { useState } from "react";
import { useRefreshTargets, useStrategy, useTargets } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { formatNumber as fmt } from "@/lib/format";
import { ErrorText } from "@/components/ui/error-text";
import { SlottedHeader } from "@/components/layout/AppPage";
import { LoadingText } from "@/components/ui/loading-text";
import { isLead, isNational, unitOf } from "./helpers";
import CountyFilter from "./CountyFilter";
import { FigureBand } from "@/components/ui/stat-tiles";
import { StatusText } from "@/components/ui/notice";

const RELIABILITY = { seat: "Seat data", typical: "Typical winner", proxy: "Proxy" };
const percent = (value, places = 1) => `${(Number(value) * 100).toFixed(places)}%`;

function Totals({ rows, label = "Seat target" }) {
  const registered = rows.reduce((s, t) => s + (t.registered_voters || 0), 0);
  const needed = rows.reduce((s, t) => s + (t.votes_needed || 0), 0);
  const turnout = rows[0]?.projected_turnout_pct;
  const figures = [["Registered voters", fmt(registered)], ["Expected turnout", turnout ? `${Number(turnout).toFixed(2)}%` : "–"], [label, fmt(needed), null, "text-accent"]];
  return <FigureBand label={label} figures={figures} />;
}

// Targets are worked out from past results; a national seat shows them a county at a time.
export default function Targets({ campaign, role }) {
  const national = isNational(campaign);
  const [place, setPlace] = useState({ county: "", constituency: "" });
  const { data, isLoading, error } = useTargets(!national || place.county ? campaign.id : undefined, place);
  const whole = useStrategy(national ? campaign.id : undefined).data;
  const refresh = useRefreshTargets();
  // Targets follow a new register or new results only when someone who runs the campaign asks.
  const action = isLead(role) ? (
    <Button loading={refresh.isPending} variant="quiet" disabled={refresh.isPending} onClick={() => refresh.mutate(campaign.id)}
      title="Work every target out again from the latest register and past results; committed votes stay.">
      {refresh.isPending ? "Refreshing…" : "Refresh targets"}
    </Button>
  ) : null;
  const { noun } = unitOf(campaign);
  const rows = data || [];
  const reliability = RELIABILITY[rows[0]?.reliability];
  return (
    <>
      <SlottedHeader context="Plan" title="Targets" sub={`The seat target is the share the last winner took, applied to the votes expected. Each ${noun} is asked for its share of where the votes were cast.`} actions={action} />
      {refresh.isSuccess && <StatusText>Refreshed: {fmt(refresh.data.units)} {noun}s, seat target {fmt(refresh.data.win_number)}.</StatusText>}
      <ErrorText error={refresh.error} />
      {national && whole && (
        <FigureBand label="National seat target" figures={[["Registered voters", fmt(whole.total_registered)], ["Projected votes cast", fmt(whole.total_cast)], ["Seat target", fmt(whole.win_number), null, "text-accent"]]} />
      )}
      {national && <CountyFilter place={place} onChange={setPlace} />}
      {national && !place.county && <p className="text-ui text-muted-foreground">Pick a county to see the targets in its wards.</p>}
      {isLoading && <LoadingText />}
      <ErrorText error={error} />
      {data && (
        <>
          <Totals rows={rows} label={national ? "Target in this area" : undefined} />
          <Card variant="outline" className="min-w-0 gap-3" role="region" aria-labelledby="targets-h">
            <CardTitle id="targets-h">Target per {noun}</CardTitle>
            <Table minWidth={600}>
              <THead><TR>
                <TH>{noun === "centre" ? "Centre" : "Ward"}</TH><TH align="right">Registered</TH><TH align="right">Share</TH><TH align="right">Target</TH>
              </TR></THead>
              <TBody>{rows.map((t) => (
                <TR key={t.id}>
                  <TD className="font-semibold">{t.centre_name || t.ward_name}</TD>
                  <TD numeric>{fmt(t.registered_voters)}</TD>
                  <TD numeric>{t.ward_weight == null ? "–" : percent(t.ward_weight, 2)}</TD>
                  <TD numeric className="font-bold">{fmt(t.votes_needed)}</TD>
                </TR>
              ))}</TBody>
            </Table>
            {reliability && <p className="text-small text-muted-foreground">Based on: {reliability}.</p>}
          </Card>
        </>
      )}
    </>
  );
}
