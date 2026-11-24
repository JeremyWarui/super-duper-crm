// /events: the campaign's coming events by month, narrowed to one ward with ?ward=.
import { Link, useSearchParams } from "react-router-dom";
import { usePublicEvents } from "@/api/hooks";
import { Card } from "@/components/ui/card";
import { FilterSelect } from "@/components/ui/input";
import { formatDay } from "@/lib/format";
import { LoadingText } from "@/components/ui/loading-text";
import { ErrorText } from "@/components/ui/error-text";
import { PageHero } from "@/components/PageHead";
import DateTile from "@/components/DateTile";
import { StoryMeta } from "@/components/ui/typography";
import { eventTime } from "./EventPage";

function byMonth(events) {
  const months = [];
  for (const e of events) {
    const name = formatDay(e.scheduled_date, { month: "long", year: "numeric" });
    if (months.at(-1)?.name !== name) months.push({ name, events: [] });
    months.at(-1).events.push(e);
  }
  return months;
}

function EventCard({ e }) {
  return (
    <Card asChild interactive className="flex-row flex-wrap items-center gap-5 p-5">
      <Link to={`/events/${e.id}`}>
        <DateTile date={e.scheduled_date} top={{ weekday: "short" }} />
        <span className="flex min-w-0 flex-[1_1_220px] flex-col gap-1.5">
          <StoryMeta category="Event" place={e.ward_name} />
          <span className="text-[20px] font-bold">{e.title}</span>
          <span className="text-[15px] text-muted-foreground">{[eventTime(e.scheduled_date), e.venue].filter(Boolean).join(" · ")}</span>
        </span>
      </Link>
    </Card>
  );
}

export default function Events() {
  const [params, setParams] = useSearchParams();
  const ward = params.get("ward") || "";
  const events = usePublicEvents();
  const all = events.data || [];
  const wards = [...new Map(all.map((e) => [e.ward, { id: e.ward, name: e.ward_name }])).values()].sort((a, b) => a.name.localeCompare(b.name));
  const months = byMonth(ward ? all.filter((e) => e.ward === ward) : all);
  const pick = (ward) => setParams(ward ? { ward } : {}, { replace: true });
  return (
    <>
      <PageHero tone="ink" crumbs={[{ label: "Events" }]} title="Events near you">
        {wards.length > 1 ? (
          <label className="flex w-full max-w-[280px] flex-col gap-1.5 text-small font-semibold text-on-dark-muted">
            Ward
            <FilterSelect label="Ward" blank="All wards" value={ward} onChange={pick} options={wards} className="w-full flex-none border-0 bg-white text-ink" />
          </label>
        ) : null}
      </PageHero>
      <div className="site-container flex flex-wrap items-start gap-10 pt-8 sm:pt-12 pb-12 sm:pb-20">
        <div className="flex min-w-0 flex-[999_1_560px] flex-col gap-3.5">
          {events.isLoading ? <LoadingText /> : null}
          {events.error ? <ErrorText error={events.error} /> : null}
          {events.isSuccess && !months.length ? <p className="text-muted-foreground">No events are planned{ward ? " in this ward" : ""} yet.</p> : null}
          {months.map((m) => (
            <section key={m.name} aria-label={m.name} className="reveal-stagger flex flex-col gap-3.5">
              <h2 className="mt-2 text-ui font-extrabold uppercase tracking-[0.12em] text-muted-foreground first:mt-0">{m.name}</h2>
              {m.events.map((e) => <EventCard key={e.id} e={e} />)}
            </section>
          ))}
        </div>
        <aside className="flex min-w-0 flex-[1_1_300px] flex-col gap-5">
          <Card variant="ink">
            <h2 className="text-[18px] font-bold">On the campaign team?</h2>
            <p className="text-[15px] text-on-dark-muted">Add events and track attendance from the workspace.</p>
            <Link to="/signin" className="font-bold text-accent hover:text-accent">Sign in →</Link>
          </Card>
        </aside>
      </div>
    </>
  );
}
