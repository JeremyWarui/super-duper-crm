// The superuser's party-wide totals, filtered by place, seat, aspirant and dates.
import { useState } from "react";
import { useAspirants, usePartyDashboard, usePartyShared } from "@/api/hooks";
import PlaceCascade from "@/components/PlaceCascade";
import { SlottedHeader } from "@/components/layout/AppPage";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorText } from "@/components/ui/error-text";
import { Field, FilterSelect, Input } from "@/components/ui/input";
import { LoadingText } from "@/components/ui/loading-text";
import { StatTiles } from "@/components/ui/stat-tiles";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { formatDate, formatNumber } from "@/lib/format";
import { AREA_LABEL, SEAT_LABEL, SEATS } from "@/lib/labels";

const EMPTY = { county: "", constituency: "", ward: "", seat: "", aspirant: "", from: "", to: "" };

function Counts({ title, head, rows }) {
  return (
    <Card variant="outline" className="min-w-0 gap-3">
      <h2 className="text-card-title font-bold">{title}</h2>
      <Table minWidth={240}>
        <THead><TR><TH>{head}</TH><TH align="right">Count</TH></TR></THead>
        <TBody>
          {rows.map(([key, label, count]) => (
            <TR key={key}><TD>{label}</TD><TD numeric className="font-semibold">{formatNumber(count)}</TD></TR>
          ))}
          {rows.length === 0 && <TR><TD colSpan={2} className="text-center text-muted-foreground">None.</TD></TR>}
        </TBody>
      </Table>
    </Card>
  );
}

const NOT_SHARED = <span className="text-muted-foreground">Not shared</span>;
const wardList = (rows) => rows.map((w) => `${w.ward} ${formatNumber(w.count)}`).join(" · ");

// The counts each hosted campaign has chosen to share; read fresh, so a switch turned off shows
// "Not shared" on the next load.
function Shared() {
  const shared = usePartyShared();
  if (shared.error) return <ErrorText error={shared.error} />;
  const rows = shared.data || [];
  return (
    <Card variant="outline" className="min-w-0 gap-3">
      <h2 className="text-card-title font-bold">Shared by campaigns</h2>
      <Table stack minWidth={720} aria-label="Shared by campaigns">
        <THead><TR><TH>Campaign</TH><TH>Event reach</TH><TH>Ward coverage</TH><TH>Supporters by ward</TH></TR></THead>
        <TBody>
          {rows.map((c) => {
            const supporters = c.supporter_counts;
            return (
              <TR key={c.id}>
                <TD className="font-semibold">{c.title}{c.seat && <div className="text-small font-normal text-muted-foreground">{SEAT_LABEL[c.seat]}</div>}</TD>
                <TD>{c.event_reach ? `${formatNumber(c.event_reach.events)} events · ${formatNumber(c.event_reach.reached)} reached · ${formatNumber(c.event_reach.attended)} attended` : NOT_SHARED}</TD>
                <TD>{c.ward_coverage ? `${formatNumber(c.ward_coverage.covered.length)} of ${formatNumber(c.ward_coverage.wards)} wards have mobilizers` : NOT_SHARED}</TD>
                <TD>
                  {supporters
                    ? `${formatNumber(supporters.reduce((n, w) => n + w.count, 0))}${supporters.length ? ` · ${wardList(supporters)}` : ""}`
                    : NOT_SHARED}
                </TD>
              </TR>
            );
          })}
          {shared.isSuccess && rows.length === 0 && <TR><TD colSpan={4} className="text-center text-muted-foreground">No nominee workspaces yet.</TD></TR>}
        </TBody>
      </Table>
    </Card>
  );
}

export default function Dashboard() {
  const [filters, setFilters] = useState(EMPTY);
  const set = (key) => (value) => setFilters({ ...filters, [key]: value });
  const board = usePartyDashboard(filters);
  const aspirants = useAspirants({ status: "approved", limit: 200 }).data?.items || [];
  const d = board.data;

  const tiles = d && [
    ["Approved members", formatNumber(d.approved_members)],
    ["Pending applications", formatNumber(d.pending_applications)],
    ["Active volunteers", formatNumber(d.active_volunteers)],
    ["Approved aspirants", formatNumber(d.approved_aspirants)],
    ["Active campaigns", formatNumber(d.active_campaigns)],
  ];

  return (
    <>
      <SlottedHeader title="Dashboard" sub="Totals across the party's registers and campaigns." />
      <Card variant="outline">
        <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-3">
          <PlaceCascade labelled place={filters} onChange={(place) => setFilters({ ...filters, ...place })} blank={() => "All"} />
          <FilterSelect labelled label="Seat" blank="All" value={filters.seat} onChange={set("seat")} options={SEATS} />
          <FilterSelect labelled label="Aspirant" blank="All" value={filters.aspirant} onChange={set("aspirant")} options={aspirants.map((a) => [a.id, `${a.member.full_name} · ${SEAT_LABEL[a.seat]}`])} />
          <Field label="From">
            <Input aria-label="From" type="date" value={filters.from} onChange={(e) => set("from")(e.target.value)} />
          </Field>
          <Field label="To">
            <Input aria-label="To" type="date" value={filters.to} onChange={(e) => set("to")(e.target.value)} />
          </Field>
        </div>
        <div className="flex justify-end">
          <Button shape="rounded" variant="quiet" onClick={() => setFilters(EMPTY)}>Clear filters</Button>
        </div>
      </Card>
      <ErrorText error={board.error} />
      {!d && !board.error && <LoadingText />}
      {d && (
        <>
          <StatTiles tiles={tiles} min={150} />
          <p className="text-small text-muted-foreground">
            Events from {formatDate(d.events_from)} to {formatDate(d.events_to)}.
          </p>
          <div className="grid gap-4 md:grid-cols-2">
            <Counts
              title="Campaigns by county and seat"
              head="County · seat"
              rows={d.campaigns_by_county_and_seat.map((r) => [`${r.county_id}-${r.seat}`, `${r.county} · ${SEAT_LABEL[r.seat]}`, r.count])}
            />
            <Counts
              title="Upcoming campaign events by county"
              head="County"
              rows={d.upcoming_events_by_county.map((r) => [r.county_id, r.county, r.count])}
            />
            <Counts
              title="Upcoming campaign events by seat"
              head="Seat"
              rows={d.upcoming_events_by_seat.map((r) => [r.seat, SEAT_LABEL[r.seat], r.count])}
            />
            <Counts
              title="Active volunteers by county"
              head="County"
              rows={d.volunteers_by_county.map((r) => [r.county_id, r.county, r.count])}
            />
            <Counts
              title="Active volunteers by area"
              head="Interest"
              rows={d.volunteers_by_interest.map((r) => [r.interest, AREA_LABEL[r.interest] || r.interest, r.count])}
            />
          </div>
          <Shared />
        </>
      )}
    </>
  );
}
