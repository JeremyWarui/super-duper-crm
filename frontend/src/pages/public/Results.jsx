// /results: the published primary results, one card per seat and area, filtered by seat.
import { useState } from "react";
import { usePublicResults } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { SEAT_LABEL, SEATS } from "@/lib/labels";
import { formatDay, formatNumber } from "@/lib/format";
import { LoadingText } from "@/components/ui/loading-text";
import { ErrorText } from "@/components/ui/error-text";
import { PageHero } from "@/components/PageHead";
import { FilterPills } from "@/components/ui/tabs";
import { StoryMeta } from "@/components/ui/typography";

/** Rows (already ordered by seat, area and votes) as races: one seat in one area, most votes first. */
export function races(rows) {
  const out = [];
  for (const r of rows) {
    const last = out.at(-1);
    if (last && last.seat === r.seat && last.area === r.area) last.rows.push(r);
    else out.push({ seat: r.seat, area: r.area, rows: [r] });
  }
  const rank = Object.fromEntries(SEATS.map(([value], n) => [value, n]));
  return out
    .map((race) => ({ ...race, declared: race.rows.every((r) => r.declared_on) ? race.rows[0].declared_on : null }))
    .sort((a, b) => rank[a.seat] - rank[b.seat]);
}

function Race({ race, label }) {
  const total = race.rows.reduce((sum, r) => sum + r.votes, 0);
  return (
    <Card asChild className="gap-3.5 p-[22px]">
      <article aria-label={`${label} · ${race.area}`}>
        <div className="flex items-start justify-between gap-2.5">
          <span className="flex flex-col gap-0.5">
            <StoryMeta category={label} />
            <strong className="text-[19px]">{race.area}</strong>
          </span>
          {race.declared ? <Badge tone="tint">Declared {formatDay(race.declared)}</Badge> : <Badge tone="stone">Counting</Badge>}
        </div>
        <ol>
          {race.rows.map((r, n) => {
            const won = race.declared && n === 0;
            return (
              <li key={r.id} className="flex justify-between gap-3 border-t border-line-soft py-2 text-[15px]">
                <span className={won ? "font-extrabold text-primary" : "font-medium"}>{won ? "✓ " : ""}{r.candidate}</span>
                <span className="font-semibold tabular-nums">{formatNumber(r.votes)} votes</span>
              </li>
            );
          })}
        </ol>
        <span className="text-small text-muted-foreground">{formatNumber(total)} votes cast</span>
      </article>
    </Card>
  );
}

export default function Results() {
  const results = usePublicResults();
  const [seat, setSeat] = useState("");
  const all = races(results.data || []);
  const shown = all.filter((r) => !seat || r.seat === seat);
  const seats = SEATS.filter(([value]) => all.some((r) => r.seat === value));
  const demo = (results.data || []).some((r) => r.demo);
  const year = all.map((r) => r.declared?.slice(0, 4)).filter(Boolean).sort().at(-1);
  return (
    <>
      <PageHero tone="ink" crumbs={[{ label: "Primary results" }]} title={<>Primary results{year ? ` ${year}` : ""}</>} lead="Results declared by the party's Elections Board for each seat and area.">
        {demo ? <p role="note" className="self-start rounded-full bg-accent px-3.5 py-1.5 text-ui font-extrabold text-ink">Demo results: made up to show how this page works.</p> : null}
      </PageHero>
      <div className="site-container flex flex-col gap-[22px] pt-9 pb-[72px]">
        {seats.length > 1 ? (
          <FilterPills look="ink" label="Seat" options={[["", "All"], ...seats.map(([value, label]) => [value, label])]} value={seat} onChange={setSeat} />
        ) : null}
        {results.isLoading ? <LoadingText /> : null}
        {results.error ? <ErrorText error={results.error} /> : null}
        {results.isSuccess && !all.length ? <p className="text-muted-foreground">No results have been declared yet.</p> : null}
        <div className="grid grid-cols-[repeat(auto-fill,minmax(min(360px,100%),1fr))] gap-[18px]">
          {shown.map((race) => <Race key={`${race.seat}-${race.area}`} race={race} label={SEAT_LABEL[race.seat]} />)}
        </div>
      </div>
    </>
  );
}
