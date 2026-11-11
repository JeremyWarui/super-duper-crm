// /events: the party's coming events by month, narrowed to one county with ?county=.
import { Link, useSearchParams } from "react-router-dom";
import { usePartyPlaces, usePublicPosts } from "@/api/hooks";
import { Card } from "@/components/ui/card";
import { FilterSelect } from "@/components/ui/input";
import { formatDay } from "@/lib/format";
import { LoadingText } from "@/components/ui/loading-text";
import { ErrorText } from "@/components/ui/error-text";
import { PageHero } from "@/components/PageHead";

function byMonth(events) {
  const months = [];
  for (const e of events) {
    const name = formatDay(e.event_date, { month: "long", year: "numeric" });
    if (months.at(-1)?.name !== name) months.push({ name, events: [] });
    months.at(-1).events.push(e);
  }
  return months;
}

function EventCard({ e }) {
  return (
    <Card asChild interactive className="flex-row flex-wrap items-center gap-5 p-5">
      <Link to={`/news/${e.id}`}>
        <span className="flex h-20 w-[72px] flex-none flex-col items-center justify-center rounded-[8px] bg-primary-tint text-primary">
          <span className="text-meta font-extrabold uppercase tracking-[0.08em]">{formatDay(e.event_date, { weekday: "short" })}</span>
          <span className="font-display text-[30px] leading-none font-extrabold">{formatDay(e.event_date, { day: "numeric" })}</span>
        </span>
        <span className="flex min-w-0 flex-[1_1_220px] flex-col gap-1.5">
          <span className="text-meta font-extrabold uppercase tracking-[0.08em] text-primary">Event{e.county ? ` · ${e.county.name}` : ""}</span>
          <span className="text-[20px] font-bold">{e.title}</span>
          {e.venue ? <span className="text-[15px] text-muted-foreground">{e.venue}</span> : null}
        </span>
      </Link>
    </Card>
  );
}

export default function Events() {
  const [params, setParams] = useSearchParams();
  const county = params.get("county") || "";
  const counties = usePartyPlaces().data || [];
  const events = usePublicPosts("event", 0, { county });
  const months = byMonth(events.data || []);
  const pick = (county) => setParams(county ? { county } : {}, { replace: true });
  return (
    <>
      <PageHero tone="ink" crumbs={[{ label: "Events" }]} title="Events near you">
        <label className="flex w-full max-w-[280px] flex-col gap-1.5 text-small font-semibold text-on-dark-muted">
          County
          <FilterSelect label="County" blank="All counties" value={county} onChange={pick} options={counties} className="w-full flex-none border-0 bg-white text-ink" />
        </label>
      </PageHero>
      <div className="site-container flex flex-wrap items-start gap-10 pt-12 pb-20">
        <div className="flex min-w-0 flex-[999_1_560px] flex-col gap-3.5">
          {events.isLoading ? <LoadingText /> : null}
          {events.error ? <ErrorText error={events.error} /> : null}
          {events.isSuccess && !months.length ? <p className="text-muted-foreground">No events are planned{county ? " in this county" : ""} yet.</p> : null}
          {months.map((m) => (
            <section key={m.name} aria-label={m.name} className="flex flex-col gap-3.5">
              <h2 className="mt-2 text-ui font-extrabold uppercase tracking-[0.12em] text-muted-foreground first:mt-0">{m.name}</h2>
              {m.events.map((e) => <EventCard key={e.id} e={e} />)}
            </section>
          ))}
        </div>
        <aside className="flex min-w-0 flex-[1_1_300px] flex-col gap-5">
          {county ? (
            <Card variant="panel" className="bg-primary-tint">
              <h2 className="text-[18px] font-bold">Your county branch</h2>
              <p className="text-[15px] text-text-2">Officials, the branch office and the next meeting.</p>
              <Link to={`/counties/${county}`} className="font-bold">See the branch →</Link>
            </Card>
          ) : null}
          <Card variant="ink">
            <h2 className="text-[18px] font-bold">Branch official or volunteer?</h2>
            <p className="text-[15px] text-on-dark-muted">Add events and track attendance from the portal.</p>
            <Link to="/signin" className="font-bold text-accent hover:text-accent">Sign in →</Link>
          </Card>
        </aside>
      </div>
    </>
  );
}
