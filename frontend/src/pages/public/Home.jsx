// The party's public homepage: carousel, agenda, news and videos, events, branches, candidates, leadership and ways to take part.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  useSite,
  usePublicBranches,
  usePublicCandidates,
  usePublicIssues,
  usePublicLeaders,
  usePublicPosts,
  usePublicSlides,
  usePublicVideos,
} from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/input";
import { SectionHead } from "@/components/ui/typography";
import { useBranding } from "@/theme/branding";
import { useCopy } from "@/copy";
import { formatDay } from "@/lib/format";
import { Photo, PHOTO_GRID, PhotoCard, QuickLinks, StoryKicker, StoryRow, VideoCard } from "./story";
import { CandidateCard } from "./Candidates";
import DateTile from "@/components/DateTile";

const ROTATE_MS = 6000;
const reducedMotion = () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
const ago = (iso) => formatDay(iso, { day: "numeric", month: "long" });
const isInternal = (url) => url.startsWith("/");

function SlideButton({ slide }) {
  if (!slide.button_label || !slide.button_url) return null;
  const props = { variant: "onDark", size: "lg" };
  return isInternal(slide.button_url) ? (
    <Button asChild {...props}><Link to={slide.button_url}>{slide.button_label}</Link></Button>
  ) : (
    <Button asChild {...props}><a href={slide.button_url}>{slide.button_label}</a></Button>
  );
}

function BranchFinder() {
  const branches = usePublicBranches().data || [];
  const [county, setCounty] = useState("");
  return (
    <aside aria-labelledby="quick-h" className="flex flex-[0_1_360px] flex-col gap-3.5 rounded-[13px] bg-white p-6 text-ink shadow-hero-card">
      <h2 id="quick-h" className="font-display text-[22px] font-extrabold">Find your branch</h2>
      <label className="flex flex-col gap-1.5 text-ui font-semibold">
        Your county
        <NativeSelect value={county} onChange={(e) => setCounty(e.target.value)}>
          <option value="">Choose a county</option>
          {branches.map((b) => <option key={b.county.id} value={b.county.id}>{b.county.name}</option>)}
        </NativeSelect>
      </label>
      <Button asChild shape="rounded" size="lg"><Link to={county ? `/counties/${county}` : "/counties"}>{county ? "Go to your branch" : "See all counties"}</Link></Button>
      <QuickLinks links={[["Events near me", "/events"], ["Check my membership", "/signin"], ["Primary results", "/results"]]} />
    </aside>
  );
}

/**
 * Rotates every 6 seconds; Pause stops it, and it never moves on its own for reduced motion.
 * `fallback` is the one slide shown when none is published; `actions` and `aside` default to the
 * party's join button and branch finder.
 */
export function Carousel({ fallback, actions, aside }) {
  const { partyName, slogan } = useBranding();
  const party = useSite().data;
  const published = usePublicSlides().data || [];
  const slides = published.length ? published : [fallback || { id: "party", kicker: partyName, headline: slogan || partyName, line: party?.description || "", image_url: "" }];
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(() => !reducedMotion());
  const count = slides.length;
  const current = slides[index % count];

  useEffect(() => {
    if (!playing || count < 2) return undefined;
    const timer = setInterval(() => setIndex((i) => (i + 1) % count), ROTATE_MS);
    return () => clearInterval(timer);
  }, [playing, count]);

  const go = (i) => setIndex(((i % count) + count) % count);
  const round = "flex size-11 cursor-pointer items-center justify-center rounded-full border-[1.5px] border-white/70 bg-black/20 text-lg text-white";
  return (
    <section aria-roledescription="carousel" aria-label="Highlights" className="relative flex min-h-[640px] items-center overflow-hidden bg-ink text-white">
      {current.image_url ? <img src={current.image_url} alt="" className="absolute inset-0 size-full object-cover" /> : null}
      <div aria-hidden className="absolute inset-0 bg-[linear-gradient(90deg,rgba(8,18,13,0.82)_0%,rgba(8,18,13,0.55)_50%,rgba(8,18,13,0.2)_100%)]" />
      <div className="site-container relative flex flex-wrap items-center justify-between gap-10 pt-16 pb-28">
        <div aria-live={playing ? "off" : "polite"} aria-roledescription="slide" aria-label={`${(index % count) + 1} of ${count}`} className="flex min-w-0 flex-[0_1_680px] flex-col gap-[22px]">
          {current.kicker ? <p className="text-ui font-bold uppercase tracking-[0.12em] text-accent">{current.kicker}</p> : null}
          <h1 className="font-display text-hero font-extrabold tracking-[-0.03em]">{current.headline}</h1>
          {current.line ? <p className="max-w-[40ch] text-[19px] leading-[1.6] text-[#ECECE7]">{current.line}</p> : null}
          <div className="flex flex-wrap gap-3 pt-1.5">
            {actions || <Button asChild variant="accent" size="lg"><Link to="/join-party">Join the party</Link></Button>}
            <SlideButton slide={current} />
          </div>
        </div>
        {aside === undefined ? <BranchFinder /> : aside}
      </div>
      {count > 1 ? (
        <div className="absolute inset-x-0 bottom-7">
          <div className="site-container flex flex-wrap items-center gap-3">
            <button type="button" aria-label="Previous slide" onClick={() => go(index - 1)} className={round}>‹</button>
            <div role="group" aria-label="Choose slide" className="flex gap-1.5">
              {slides.map((s, i) => (
                <button
                  key={s.id}
                  type="button"
                  aria-label={`Slide ${i + 1}`}
                  aria-current={i === index % count ? "true" : undefined}
                  onClick={() => go(i)}
                  className="flex h-11 min-w-11 cursor-pointer items-center justify-center bg-transparent"
                >
                  <span className={i === index % count ? "h-2.5 w-7 rounded-full bg-accent" : "size-2.5 rounded-full bg-white/60"} />
                </button>
              ))}
            </div>
            <button type="button" aria-label="Next slide" onClick={() => go(index + 1)} className={round}>›</button>
            <button type="button" onClick={() => setPlaying(!playing)} className="h-11 cursor-pointer rounded-full border-[1.5px] border-white/70 bg-black/20 px-3.5 text-small font-bold text-white">
              {playing ? "Pause" : "Play"}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}

export function Ticker({ news }) {
  if (!news.length) return null;
  return (
    <div className="border-b border-line-2 bg-white">
      <div className="site-container flex flex-wrap items-center gap-x-7 gap-y-3 py-3.5">
        <span className="rounded-sm bg-ink px-2.5 py-1.5 text-meta font-extrabold uppercase tracking-[0.12em] text-accent">Latest</span>
        {news.slice(0, 3).map((n) => <Link key={n.id} to={`/news/${n.id}`} className="text-body font-semibold text-ink no-underline hover:text-primary">{n.title}</Link>)}
      </div>
    </div>
  );
}

export function Agenda({ limit }) {
  const more = useCopy().agendaMore;
  const all = usePublicIssues().data || [];
  const issues = limit ? all.slice(0, limit) : all;
  if (!issues.length) return null;
  return (
    <section id="issues" className="scroll-mt-24 bg-white">
      <div className="site-container flex flex-col gap-8 py-20">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex max-w-[640px] flex-col gap-2.5">
            <p className="kicker">Our agenda</p>
            <h2 className="font-display text-section font-extrabold tracking-[-0.02em]">Where we stand</h2>
          </div>
          <Link to={more.to} className="font-bold">{more.label}</Link>
        </div>
        <div className={PHOTO_GRID}>
          {issues.map((i) => (
            <PhotoCard key={i.id} to={`/issues/${i.id}`} image={i.image_url} title={i.title} foot={<span className="mt-2.5 text-ui font-bold text-accent">Our position →</span>} />
          ))}
        </div>
      </div>
    </section>
  );
}

export function Watch() {
  const videos = (usePublicVideos().data || []).slice(0, 3);
  const youtube = Object.entries(useSite().data?.social_links || {}).find(([name]) => /youtube/i.test(name))?.[1];
  if (!videos.length) return null;
  return (
    <section aria-labelledby="watch-h" className="flex flex-col gap-4 border-t-[3px] border-ink pt-3.5">
      <div className="flex items-baseline justify-between gap-3">
        <h3 id="watch-h" className="font-display text-2xl font-extrabold">Watch</h3>
        {youtube ? <a href={youtube} target="_blank" rel="noreferrer" className="font-bold">All videos →</a> : null}
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-4">
        {videos.map((v) => <VideoCard key={v.id} video={v} />)}
      </div>
    </section>
  );
}

export function News({ news }) {
  const kicker = useCopy().newsKicker;
  if (!news.length) return null;
  const [lead, ...rest] = news;
  return (
    <section id="news" className="bg-stone">
      <div className="site-container flex flex-col gap-7 py-20">
        <SectionHead kicker={kicker} title="News & statements" action={{ label: "All news", to: "/news" }} />
        <div className="flex flex-wrap gap-7">
          <Link to={`/news/${lead.id}`} className="flex min-w-0 flex-[3_1_460px] flex-col gap-3.5 text-ink no-underline hover:text-ink">
            <Photo url={lead.image_url} className="aspect-video w-full rounded-card" />
            <span className="flex flex-wrap items-center gap-2.5">
              <StoryKicker post={lead} />
              <span className="text-meta font-extrabold uppercase tracking-[0.1em] text-muted-foreground">{ago(lead.published_on)}</span>
            </span>
            <span className="font-display text-[30px] leading-[1.15] font-extrabold tracking-[-0.01em]">{lead.title}</span>
            {lead.excerpt ? <span className="line-clamp-2 leading-[1.6] text-muted-foreground">{lead.excerpt}</span> : null}
            <span className="text-small text-muted-foreground">{lead.author ? `By ${lead.author} · ` : ""}{lead.read_minutes} min read</span>
          </Link>
          <div className="flex min-w-0 flex-[2_1_320px] flex-col">
            {rest.slice(0, 3).map((n) => (
              <StoryRow key={n.id} post={n} when={ago(n.published_on)} photoClass="h-[76px] w-[104px]" />
            ))}
          </div>
        </div>
        <Watch />
      </div>
    </section>
  );
}

export function Events() {
  const events = usePublicPosts("event").data || [];
  if (!events.length) return null;
  return (
    <section id="events" className="bg-ink text-on-dark">
      <div className="site-container flex flex-col gap-7 py-[72px]">
        <SectionHead kicker="Coming up" title="Upcoming events" action={{ label: "Full calendar", to: "/events" }} onDark />
        <div className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-4">
          {events.slice(0, 3).map((e) => (
            <Link key={e.id} to={`/news/${e.id}`} className="flex flex-col gap-3.5 rounded-photo border border-ink-2 p-[22px] text-on-dark no-underline hover:text-white">
              <DateTile date={e.event_date} tone="accent" />
              <span className="text-[19px] leading-[1.3] font-bold">{e.title}</span>
              {e.venue ? <span className="text-ui text-on-dark-muted">{e.venue}</span> : null}
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}

function Branches() {
  const branches = usePublicBranches().data || [];
  const [county, setCounty] = useState("");
  if (!branches.length) return null;
  const b = branches.find((x) => x.county.id === county);
  return (
    <section id="branches" className="bg-mint">
      <div className="site-container flex flex-wrap items-center gap-10 py-20">
        <div className="flex min-w-0 flex-[1_1_380px] flex-col gap-4">
          <p className="kicker">In all {branches.length} counties</p>
          <h2 className="font-display text-section font-extrabold tracking-[-0.02em]">Find your branch</h2>
          <p className="text-lead text-text-2">Meet your county officials, attend local meetings and get involved where you live.</p>
          <label className="flex max-w-[360px] flex-col gap-1.5 text-ui font-semibold">
            County
            <NativeSelect value={county} onChange={(e) => setCounty(e.target.value)}>
              <option value="">Choose a county</option>
              {branches.map((x) => <option key={x.county.id} value={x.county.id}>{x.county.name}</option>)}
            </NativeSelect>
          </label>
        </div>
        <Card variant="elevated" className="min-w-0 flex-[1_1_420px] rounded-panel p-7">
          {b ? (
            <>
              <h3 className="text-h3 font-bold">{b.county.name} branch</h3>
              <div className="flex flex-col gap-2 text-body">
                {b.officials.filter((o) => o.office === "chair" || o.office === "secretary").map((o) => (
                  <span key={o.office}><strong>{o.label}:</strong> {o.name}</span>
                ))}
                {b.office_address ? <span><strong>Office:</strong> {[b.office_address, b.phone].filter(Boolean).join(" · ")}</span> : null}
                {b.next_meeting_on ? <span><strong>Next branch meeting:</strong> {ago(b.next_meeting_on)}{b.next_meeting_venue ? `, ${b.next_meeting_venue}` : ""}</span> : null}
              </div>
              <Link to={`/counties/${b.county.id}`} className="font-bold">Visit the {b.county.name} branch page →</Link>
            </>
          ) : (
            <>
              <span className="text-lead font-bold">Choose a county to see its branch</span>
              <span className="text-muted-foreground">Officials, office address and the next branch meeting appear here.</span>
            </>
          )}
        </Card>
      </div>
    </section>
  );
}

function OurCandidates() {
  const people = (usePublicCandidates().data || []).slice(0, 4);
  if (!people.length) return null;
  return (
    <section id="candidates" className="bg-white">
      <div className="site-container flex flex-col gap-7 py-20">
        <SectionHead kicker="On the ballot" title="Our candidates" action={{ label: "All candidates by county", to: "/candidates" }} />
        <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-5">
          {people.map((c) => <CandidateCard key={c.slug} c={c} square />)}
        </div>
      </div>
    </section>
  );
}

function Leadership() {
  const leaders = usePublicLeaders().data || [];
  if (!leaders.length) return null;
  return (
    <section id="about" className="bg-primary text-white">
      <div className="site-container flex flex-col gap-7 py-[72px]">
        <SectionHead kicker="Who leads us" title="Party leadership" action={{ label: "Meet the leadership", to: "/leadership" }} onDark />
        <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-5">
          {leaders.slice(0, 4).map((l) => (
            <div key={l.id} className="flex items-center gap-3.5">
              {l.photo_url ? <img src={l.photo_url} alt="" className="size-[72px] flex-none rounded-full border-2 border-accent object-cover" /> : <span className="size-[72px] flex-none rounded-full border-2 border-accent bg-white/20" />}
              <span className="flex flex-col gap-0.5">
                <span className="font-bold">{l.name}</span>
                <span className="text-ui text-on-primary-muted">{l.position}</span>
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

const PANEL = "flex flex-col gap-3.5 rounded-panel p-8";
const PANEL_TITLE = "font-display text-[28px] font-extrabold";

/** One of the three take-part panels; `tone` is "accent", "primary" or "card". */
function TakePanel({ tone, title, text, action }) {
  if (tone === "card") {
    return (
      <Card variant="elevated" className={`${PANEL} p-8`}>
        <h3 className={PANEL_TITLE}>{title}</h3>
        <p className="text-text-2">{text}</p>
        <div className="mt-auto self-start">{action}</div>
      </Card>
    );
  }
  const accent = tone === "accent";
  return (
    <div className={`${PANEL} ${accent ? "bg-accent text-ink" : "bg-primary text-white"}`}>
      <h3 className={PANEL_TITLE}>{title}</h3>
      <p className={accent ? "text-[#3B3415]" : "text-on-primary-muted"}>{text}</p>
      <div className="mt-auto self-start">{action}</div>
    </div>
  );
}

const PARTY_PANELS = [
  { tone: "accent", title: "Join the party", text: "Become a registered member and have a say in your branch.", action: <Button asChild variant="ink"><Link to="/join-party">Register as a member</Link></Button> },
  { tone: "primary", title: "Vie with us", text: "Seeking a seat? Learn how to become an aspirant and get the party's campaign tools.", action: <Button asChild variant="accent"><Link to="/vie">Become an aspirant</Link></Button> },
  { tone: "card", title: "Contribute", text: "Support the party's work in every county.", action: <Button asChild variant="ink"><Link to="/contribute">Give now</Link></Button> },
];

/** "Three ways to take part": the party's panels unless others are given. */
export function TakePart({ panels = PARTY_PANELS }) {
  return (
    <section id="take-part" className="bg-white">
      <div className="site-container flex flex-col gap-7 py-20">
        <SectionHead kicker="Get involved" title="Three ways to take part" />
        <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-5">
          {panels.map((panel) => <TakePanel key={panel.title} {...panel} />)}
        </div>
      </div>
    </section>
  );
}

export default function Home() {
  const news = usePublicPosts("news").data || [];
  return (
    <>
      <Carousel />
      <Ticker news={news} />
      <Agenda />
      <News news={news} />
      <Events />
      <Branches />
      <OurCandidates />
      <Leadership />
      <TakePart />
    </>
  );
}
