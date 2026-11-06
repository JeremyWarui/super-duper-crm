// /counties/:id: a county branch's officials, coming events, sub-branches, office and next meeting.
import { Link, useParams } from "react-router-dom";
import { usePublicBranch, usePublicPosts } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Crumbs } from "@/components/ui/typography";

const day = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "long", year: "numeric" });

export default function Branch() {
  const { id } = useParams();
  const branch = usePublicBranch(id);
  const events = usePublicPosts("event", 0, { county: id }).data || [];
  if (branch.isLoading) return <div className="site-container py-12 text-muted-foreground">Loading…</div>;
  if (branch.error) return <div role="alert" className="site-container py-12">{branch.error.message}</div>;
  const b = branch.data;
  const officials = b.officials.map((o) => [o.label, o.name]);
  const wards = b.constituencies.reduce((n, k) => n + k.wards.length, 0);
  return (
    <>
      <section className="bg-primary-tint">
        <div className="site-container flex flex-wrap items-end justify-between gap-6 py-11">
          <div className="flex flex-col gap-2.5">
            <Crumbs items={[{ label: "Home", to: "/" }, { label: "Counties", to: "/counties" }, { label: b.county.name }]} />
            <h1 className="font-display text-[clamp(40px,5vw,60px)] font-extrabold tracking-[-0.03em]">{b.county.name} County branch</h1>
            <p className="text-[17px] text-text-2">{b.constituencies.length} constituency sub-branches · {wards} wards</p>
          </div>
          <div className="flex flex-wrap gap-2.5">
            <Button asChild><Link to="/join-party">Join this branch</Link></Button>
            <Button asChild variant="outline"><a href="#office">Visit the office</a></Button>
          </div>
        </div>
      </section>
      <div className="site-container flex flex-col gap-10 pt-11 pb-[72px]">
        {officials.length ? (
          <section aria-labelledby="officials-h" className="flex flex-col gap-[18px]">
            <h2 id="officials-h" className="border-t-[3px] border-ink pt-3.5 font-display text-[32px] font-extrabold">Branch officials</h2>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-4">
              {officials.map(([role, name], i) => (
                <Card key={`${role}-${i}`} className="gap-0.5 p-3.5">
                  <strong>{name}</strong>
                  <span className="text-ui text-muted-foreground">{role}</span>
                </Card>
              ))}
            </div>
          </section>
        ) : null}
        <div className="flex flex-wrap items-start gap-6">
          <Card className="min-w-0 flex-[3_1_460px] gap-2.5">
            {events.length ? (
              <>
                <h2 className="text-[22px] font-bold">Upcoming in {b.county.name}</h2>
                {events.slice(0, 3).map((e) => (
                  <Link key={e.id} to={`/news/${e.id}`} className="flex flex-col gap-0.5 border-t border-line-soft py-3 text-ink no-underline hover:text-primary">
                    <strong>{e.title}</strong>
                    <span className="text-ui text-muted-foreground">{day(e.event_date)}{e.venue ? ` · ${e.venue}` : ""}</span>
                  </Link>
                ))}
                <Link to={`/events?county=${id}`} className="text-ui font-bold">All events in {b.county.name} →</Link>
              </>
            ) : null}
            <h2 className={events.length ? "pt-4 text-[22px] font-bold" : "text-[22px] font-bold"}>Next meeting</h2>
            {b.next_meeting_on ? (
              <p className="text-body"><strong>{day(b.next_meeting_on)}</strong>{b.next_meeting_venue ? ` · ${b.next_meeting_venue}` : ""}</p>
            ) : (
              <p className="text-body text-muted-foreground">No meeting is set yet.</p>
            )}
            <h2 className="pt-4 text-[22px] font-bold">Sub-branches</h2>
            <div className="flex flex-col gap-3">
              {b.constituencies.map((k) => (
                <div key={k.id} className="flex flex-col gap-1.5">
                  <span className="font-bold">{k.name}</span>
                  <div className="flex flex-wrap gap-2">
                    {k.wards.map((w) => <span key={w.id} className="rounded-full bg-ground-app px-3.5 py-2 text-ui font-semibold">{w.name}</span>)}
                  </div>
                </div>
              ))}
            </div>
          </Card>
          <section id="office" aria-labelledby="office-h" className="flex flex-[2_1_320px] flex-col gap-2 rounded-card bg-ink p-[22px] text-on-dark">
            <h2 id="office-h" className="pb-1 text-[20px] font-bold">Branch office</h2>
            {b.office_address ? <span>{b.office_address}</span> : null}
            {[b.phone, b.email].filter(Boolean).length ? <span>{[b.phone, b.email].filter(Boolean).join(" · ")}</span> : null}
            {!b.office_address && !b.phone && !b.email ? <span className="text-on-dark-muted">Contact the party office.</span> : null}
          </section>
        </div>
      </div>
    </>
  );
}
