// The superuser's party-wide totals, filtered by place, seat, aspirant and dates.
import { useState } from "react";
import { useAspirants, usePartyDashboard, usePartyPlaces, usePartyShared } from "../../api/hooks";
import { Button, ErrorState, Field, LoadingState, PageTitle, Panel } from "../../components/ui";
import { formatDate, formatNumber } from "../../lib/format";
import { AREA_LABEL, SEAT_LABEL, SEATS } from "./helpers";

const EMPTY = { county: "", constituency: "", ward: "", seat: "", aspirant: "", from: "", to: "" };

function Pick({ label, value, onChange, options, disabled }) {
  return (
    <Field label={label}>
      <select aria-label={label} className="app-field" value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
        <option value="">All</option>
        {options.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
      </select>
    </Field>
  );
}

function Counts({ title, head, rows }) {
  return (
    <Panel pad={0}>
      <div className="card-head"><div className="card-title">{title}</div></div>
      <div className="table-scroll">
        <table className="table">
          <thead><tr><th>{head}</th><th className="num">Count</th></tr></thead>
          <tbody>
            {rows.map(([key, label, count]) => (
              <tr key={key}><td>{label}</td><td className="num figure">{formatNumber(count)}</td></tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={2} className="empty-row">None.</td></tr>}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

const NOT_SHARED = <span className="muted">Not shared</span>;
const wardList = (rows) => rows.map((w) => `${w.ward} ${formatNumber(w.count)}`).join(" · ");

// The counts each hosted campaign has chosen to share; read fresh, so a switch turned off shows
// "Not shared" on the next load.
function Shared() {
  const shared = usePartyShared();
  if (shared.error) return <ErrorState error={shared.error} />;
  const rows = shared.data || [];
  return (
    <Panel pad={0}>
      <div className="card-head"><div className="card-title">Shared by campaigns</div></div>
      <div className="table-scroll">
        <table className="table" aria-label="Shared by campaigns">
          <thead><tr><th>Campaign</th><th>Event reach</th><th>Ward coverage</th><th>Supporters by ward</th></tr></thead>
          <tbody>
            {rows.map((c) => {
              const supporters = c.supporter_counts;
              return (
                <tr key={c.id}>
                  <td className="strong">{c.title}{c.seat && <div className="muted">{SEAT_LABEL[c.seat]}</div>}</td>
                  <td>{c.event_reach ? `${formatNumber(c.event_reach.events)} events · ${formatNumber(c.event_reach.reached)} reached · ${formatNumber(c.event_reach.attended)} attended` : NOT_SHARED}</td>
                  <td>{c.ward_coverage ? `${formatNumber(c.ward_coverage.covered.length)} of ${formatNumber(c.ward_coverage.wards)} wards have mobilizers` : NOT_SHARED}</td>
                  <td>
                    {supporters
                      ? `${formatNumber(supporters.reduce((n, w) => n + w.count, 0))}${supporters.length ? ` · ${wardList(supporters)}` : ""}`
                      : NOT_SHARED}
                  </td>
                </tr>
              );
            })}
            {shared.isSuccess && rows.length === 0 && <tr><td colSpan={4} className="empty-row">No nominee workspaces yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

export default function Dashboard() {
  const [filters, setFilters] = useState(EMPTY);
  const set = (key) => (value) => {
    const next = { ...filters, [key]: value };
    // A narrower place belongs to the wider one; changing the wider clears it.
    if (key === "county") Object.assign(next, { constituency: "", ward: "" });
    if (key === "constituency") next.ward = "";
    setFilters(next);
  };
  const board = usePartyDashboard(filters);
  const counties = usePartyPlaces().data || [];
  const constituencies = usePartyPlaces({ county: filters.county, enabled: !!filters.county }).data || [];
  const wards = usePartyPlaces({ constituency: filters.constituency, enabled: !!filters.constituency }).data || [];
  const aspirants = useAspirants({ status: "approved", limit: 200 }).data?.items || [];
  const places = (rows) => rows.map((p) => [p.id, p.name]);
  const d = board.data;

  const tiles = d && [
    ["Approved members", formatNumber(d.approved_members)],
    ["Pending applications", formatNumber(d.pending_applications)],
    ["Active volunteers", formatNumber(d.active_volunteers)],
    ["Approved aspirants", formatNumber(d.approved_aspirants)],
    ["Active campaigns", formatNumber(d.active_campaigns)],
  ];

  return (
    <div>
      <PageTitle title="Dashboard" sub="Totals across the party's registers and campaigns." />
      <Panel pad={18}>
        <div className="filter-grid">
          <Pick label="County" value={filters.county} onChange={set("county")} options={places(counties)} />
          <Pick label="Constituency" value={filters.constituency} onChange={set("constituency")} options={places(constituencies)} disabled={!filters.county} />
          <Pick label="Ward" value={filters.ward} onChange={set("ward")} options={places(wards)} disabled={!filters.constituency} />
          <Pick label="Seat" value={filters.seat} onChange={set("seat")} options={SEATS.map(([value, label]) => [value, label])} />
          <Pick label="Aspirant" value={filters.aspirant} onChange={set("aspirant")} options={aspirants.map((a) => [a.id, `${a.member.full_name} · ${SEAT_LABEL[a.seat]}`])} />
          <Field label="From">
            <input aria-label="From" type="date" className="app-field" value={filters.from} onChange={(e) => set("from")(e.target.value)} />
          </Field>
          <Field label="To">
            <input aria-label="To" type="date" className="app-field" value={filters.to} onChange={(e) => set("to")(e.target.value)} />
          </Field>
        </div>
        <div className="flex justify-end form-actions">
          <Button onClick={() => setFilters(EMPTY)}>Clear filters</Button>
        </div>
      </Panel>
      {board.error && <ErrorState error={board.error} />}
      {!d && !board.error && <LoadingState />}
      {d && (
        <>
          <div className="kpi-grid">
            {tiles.map(([label, value]) => (
              <Panel key={label} pad={20} className="kpi">
                <div className="kpi-label">{label}</div>
                <div className="kpi-value">{value}</div>
              </Panel>
            ))}
          </div>
          <div className="page-note">
            Events from {formatDate(d.events_from)} to {formatDate(d.events_to)}.
          </div>
          <div className="grid overview-grid gap-4">
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
    </div>
  );
}
