// An aspirant installation's website: the homepage, and its About, Agenda and Media pages.
import { useState } from "react";
import { Link } from "react-router-dom";
import { FileText } from "lucide-react";
import { usePublicDocuments, usePublicPosts, usePublicVideos, useSiteCandidate, useSiteVolunteer } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { SectionHead } from "@/components/ui/typography";
import { CandidateView, SEAT_TITLE, VolunteerDialog } from "./Candidate";
import { Agenda, Carousel, Events, News, TakePart, Ticker, youtubeThumb } from "./Home";
import PageHead from "./PageHead";
import { Photo } from "./story";

const WITHDRAW = "/volunteer/withdraw/";
const firstName = (c) => c.name.split(/\s+/)[0];

function ComingSoon() {
  return (
    <div className="site-container py-12">
      <PageHead title="Coming soon" lead="The campaign is preparing this page. Check back shortly." />
    </div>
  );
}

function Loading() {
  return <div className="site-container py-12 text-muted-foreground">Loading…</div>;
}

/** `photo` is left out when the candidate's hero above already shows it. */
/** Beside the carousel, where the party's homepage has its branch finder. */
function CandidateCard({ c }) {
  return (
    <aside aria-labelledby="who-h" className="flex flex-[0_1_360px] flex-col gap-3.5 rounded-[13px] bg-white p-6 text-ink shadow-hero-card">
      <div className="flex items-center gap-3.5">
        <Photo url={c.photo_url} className="size-[72px] flex-none rounded-full bg-primary-tint" />
        <span className="flex flex-col gap-0.5">
          <h2 id="who-h" className="font-display text-[22px] leading-tight font-extrabold">{c.name}</h2>
          <span className="text-ui text-muted-foreground">{SEAT_TITLE[c.seat]} · {c.area}</span>
        </span>
      </div>
      <div className="flex flex-col border-t border-line-2">
        {[["About " + firstName(c), "/about"], ["The agenda", "/agenda"], ["Events near me", "/events"], ["Contribute", "/contribute"]].map(([label, to]) => (
          <Link key={to} to={to} className="flex justify-between border-b border-line-soft py-3 font-semibold text-ink no-underline last:border-0 hover:text-primary">
            <span>{label}</span><span aria-hidden>→</span>
          </Link>
        ))}
      </div>
    </aside>
  );
}

/** Where the party's homepage shows its leadership: the candidate. */
function Candidate({ c }) {
  const first = firstName(c);
  const lead = (c.bio || "").split(/\n+/).find(Boolean);
  return (
    <section id="about" className="bg-primary text-white">
      <div className="site-container flex flex-col gap-7 py-[72px]">
        <SectionHead kicker="Who is standing" title={`Why ${first}?`} action={{ label: `More about ${first}`, to: "/about" }} onDark />
        <div className="flex flex-wrap items-center gap-8">
          {c.photo_url ? <img src={c.photo_url} alt="" className="size-[120px] flex-none rounded-full border-2 border-accent object-cover" /> : <span className="size-[120px] flex-none rounded-full border-2 border-accent bg-white/20" />}
          <div className="flex min-w-0 flex-[1_1_420px] flex-col gap-3">
            {lead ? <p className="text-[18px] leading-[1.7] text-[#CFE0D5]">{lead}</p> : null}
            {c.priorities.length ? (
              <ul className="flex flex-wrap gap-x-6 gap-y-2">
                {c.priorities.map((p, n) => <li key={n} className="font-bold"><span className="text-accent">{n + 1}</span> {p.title}</li>)}
              </ul>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}

export default function AspirantHome() {
  const page = useSiteCandidate();
  const send = useSiteVolunteer();
  const news = usePublicPosts("news").data || [];
  const [volunteering, setVolunteering] = useState(false);
  if (page.isLoading) return <Loading />;
  if (page.error) return <ComingSoon />;
  const c = page.data;
  const first = firstName(c);
  const open = () => setVolunteering(true);
  const volunteer = c.volunteering_open
    ? <Button variant="accent" size="lg" onClick={open}>Volunteer for {first}</Button>
    : <Button asChild variant="accent" size="lg"><Link to="/about">Meet {first}</Link></Button>;
  const panels = [
    {
      tone: "accent",
      title: "Volunteer",
      text: "Mobilise your ward, host a baraza or help on polling day.",
      action: c.volunteering_open ? <Button variant="ink" onClick={open}>Volunteer for {first}</Button> : <Button asChild variant="ink"><Link to="/volunteer">Volunteer</Link></Button>,
    },
    { tone: "primary", title: `Meet ${first}`, text: "Who is standing, and what the campaign will do.", action: <Button asChild variant="accent"><Link to="/about">About {first}</Link></Button> },
    { tone: "card", title: "Contribute", text: "Support the campaign's work on the ground.", action: <Button asChild variant="ink"><Link to="/contribute">Give now</Link></Button> },
  ];
  return (
    <>
      <Carousel actions={volunteer} aside={<CandidateCard c={c} />} />
      <Ticker news={news} />
      <Agenda limit={6} />
      <News news={news} />
      <Events />
      <Candidate c={c} />
      <TakePart panels={panels} />
      {volunteering ? <VolunteerDialog c={c} send={send} withdrawPath={WITHDRAW} onClose={() => setVolunteering(false)} /> : null}
    </>
  );
}

/** /about: the candidate's full profile. */
export function AspirantAbout() {
  const page = useSiteCandidate();
  const send = useSiteVolunteer();
  if (page.isLoading) return <Loading />;
  if (page.error) return <ComingSoon />;
  return <CandidateView c={page.data} send={send} withdrawPath={WITHDRAW} crumbs={[{ label: "Home", to: "/" }, { label: "About" }]} />;
}

/** /agenda: every published agenda issue. */
export function AspirantAgenda() {
  return (
    <>
      <div className="site-container pt-12"><PageHead title="Agenda" lead="Where the campaign stands, issue by issue." /></div>
      <Agenda />
    </>
  );
}

/** /media: every published video and document. */
export function AspirantMedia() {
  const videos = usePublicVideos().data || [];
  const documents = usePublicDocuments().data || [];
  return (
    <div className="site-container flex flex-col gap-12 pt-12 pb-20">
      <PageHead title="Videos & documents" lead="Speeches, interviews and the campaign's own papers." />
      {videos.length ? (
        <section aria-labelledby="videos-h" className="flex flex-col gap-4">
          <h2 id="videos-h" className="rule-top font-display text-[28px] font-extrabold">Videos</h2>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-5">
            {videos.map((v) => {
              const thumb = v.thumbnail_url || youtubeThumb(v.url);
              return (
                <a key={v.id} href={v.url} target="_blank" rel="noreferrer" className="flex flex-col gap-2 text-ink no-underline hover:text-primary">
                  <span className="relative block aspect-video overflow-hidden rounded-photo bg-[#34443B]">{thumb ? <img src={thumb} alt="" className="absolute inset-0 size-full object-cover" /> : null}</span>
                  <span className="font-bold">{v.title}</span>
                  {v.duration ? <span className="text-small text-muted-foreground">{v.duration}</span> : null}
                </a>
              );
            })}
          </div>
        </section>
      ) : null}
      {documents.length ? (
        <section aria-labelledby="docs-h" className="flex flex-col gap-4">
          <h2 id="docs-h" className="rule-top font-display text-[28px] font-extrabold">Documents</h2>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-3">
            {documents.map((d) => (
              <Card key={d.id} asChild interactive className="flex-row items-center gap-3 p-4">
                <a href={d.url} target="_blank" rel="noreferrer" className="text-ink no-underline"><FileText aria-hidden className="size-5 flex-none text-primary" /><span className="font-bold">{d.title}</span></a>
              </Card>
            ))}
          </div>
        </section>
      ) : null}
      {!videos.length && !documents.length ? <p className="text-muted-foreground">Nothing published here yet.</p> : null}
    </div>
  );
}
