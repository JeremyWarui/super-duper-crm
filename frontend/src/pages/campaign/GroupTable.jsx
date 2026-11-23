import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { formatNumber as fmt } from "@/lib/format";
import { statusOf } from "./helpers";

const TONE = { good: "ok", warn: "warn", bad: "bad" };
const LEVEL = { county: ["County", "Counties"], constituency: ["Constituency", "Constituencies"] };

/** The strategy's units rolled up by county or constituency; `onPick` opens one. */
export default function GroupTable({ level, groups, onPick }) {
  const [Noun, Nouns] = LEVEL[level];
  return (
    <Card variant="outline" className="min-w-0 gap-3" role="region" aria-labelledby="groups-h">
      <CardTitle id="groups-h">{Nouns}</CardTitle>
      <Table stack minWidth={620}>
        <THead><TR>
          <TH>{Noun}</TH><TH align="right">Wards</TH><TH align="right">Win number</TH><TH align="right">Committed</TH><TH align="right">No mobilizer</TH><TH>Status</TH>
        </TR></THead>
        <TBody>{groups.map((g) => {
          const st = statusOf(g.progress);
          return (
            <TR key={g.id}>
              <TD>{onPick ? <Button variant="quiet" size="sm" onClick={() => onPick(g.id)}>{g.name}</Button> : <span className="font-semibold">{g.name}</span>}</TD>
              <TD numeric>{fmt(g.units)}</TD>
              <TD numeric className="font-bold">{fmt(g.needed)}</TD>
              <TD numeric>{fmt(g.committed)} <span className="text-small text-muted-foreground">· {Math.round(g.progress * 100)}%</span></TD>
              <TD numeric className={g.unstaffed ? "font-semibold text-bad-foreground" : undefined}>{fmt(g.unstaffed)}</TD>
              <TD><Badge tone={TONE[st.tone]}>{st.label}</Badge></TD>
            </TR>
          );
        })}</TBody>
      </Table>
    </Card>
  );
}
