// /events/:id: one event the campaign put on the website, with a link to register while sign-ups are open.
import { Link, useParams } from "react-router-dom";
import { CalendarDays, MapPin } from "lucide-react";
import { usePublicEvent } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { PageHero } from "@/components/PageHead";
import { pageState } from "@/components/PageState";
import { formatDay, linesOf } from "@/lib/format";
import { Photo } from "./story";

/** "10:00" in Nairobi, or nothing for an event booked without a time (stored as midnight UTC). */
export function eventTime(value) {
  if (!value) return "";
  const at = new Date(value);
  if (!at.getUTCHours() && !at.getUTCMinutes()) return "";
  return at.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Africa/Nairobi" });
}

export default function EventPage() {
  const { id } = useParams();
  const event = usePublicEvent(id);
  const state = pageState(event);
  if (state) return state;
  const e = event.data;
  const when = [formatDay(e.scheduled_date, { weekday: "long", day: "numeric", month: "long", year: "numeric" }), eventTime(e.scheduled_date)].filter(Boolean).join(" · ");
  return (
    <>
      <PageHero tone="ink" crumbs={[{ label: "Events", to: "/events" }, { label: e.title }]} kicker={`Event · ${e.ward_name}`} title={e.title}>
        <div className="flex flex-col gap-2 text-lead text-on-dark-muted">
          {when ? <span className="flex items-center gap-2"><CalendarDays className="size-5 text-accent" aria-hidden />{when}</span> : null}
          {e.venue ? <span className="flex items-center gap-2"><MapPin className="size-5 text-accent" aria-hidden />{e.venue}, {e.ward_name}</span> : null}
        </div>
        {e.signup_code ? <div><Button asChild variant="accent" size="lg"><Link to={`/join/${e.signup_code}`}>Register to attend</Link></Button></div> : null}
      </PageHero>
      <div className="site-container grid items-start gap-8 py-10 sm:py-14 md:grid-cols-2 md:gap-14">
        {e.image_url ? <Photo url={e.image_url} alt={e.title} className="aspect-[4/3] w-full rounded-card" /> : null}
        <div className="flex max-w-[68ch] min-w-0 flex-col gap-4">
          {linesOf(e.description).map((p, n) => <p key={n} className="text-lead text-text-2">{p}</p>)}
          {!e.description ? <p className="text-lead text-text-2">Come and meet the campaign. Everyone is welcome.</p> : null}
          <Link to="/events" className="font-bold">All events →</Link>
        </div>
      </div>
    </>
  );
}
