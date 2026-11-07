// An aspirant installation's website: the homepage, and its About, Agenda and Media pages.
import { useState } from "react";
import { Link } from "react-router-dom";
import { FileText } from "lucide-react";
import { usePublicDocuments, usePublicPosts, usePublicSlides, usePublicVideos, useSiteCandidate, useSiteVolunteer } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { SectionHead } from "@/components/ui/typography";
import { CandidateHero, CandidateView, SEAT_TITLE, SupportCard, VolunteerDialog } from "./Candidate";
import { Agenda, Carousel, Events, News, Ticker, youtubeThumb } from "./Home";
import PageHead from "./PageHead";
import { Photo } from "./story";

const WITHDRAW = "/volunteer/withdraw/";
const AMOUNTS = [200, 500, 1000, 2500, 5000];
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
function Why({ c, photo }) {
  const first = firstName(c);
  const lead = (c.bio || "").split(/\n+/).find(Boolean);
  return (
    <section aria-labelledby="why-h" className="bg-white">
      <div className="site-container flex flex-wrap items-center gap-10 py-20">
        {photo ? <Photo url={c.photo_url} className="aspect-[4/5] w-full max-w-[360px] flex-none rounded-band bg-primary-tint" /> : null}
        <div className="flex min-w-0 flex-[1_1_420px] flex-col gap-4">
          <p className="kicker">{SEAT_TITLE[c.seat]} · {c.area}</p>
          <h2 id="why-h" className="font-display text-section font-extrabold tracking-[-0.02em]">Why {first}?</h2>
          {lead ? <p className="text-[18px] leading-[1.7] text-text-2">{lead}</p> : null}
          {c.priorities.length ? (
            <ul className="flex flex-col gap-2">
              {c.priorities.map((p, n) => (
                <li key={n} className="flex gap-3">
                  <span className="font-display font-extrabold text-primary">{n + 1}</span>
                  <span><strong>{p.title}</strong>{p.text ? <span className="text-muted-foreground"> · {p.text}</span> : null}</span>
                </li>
              ))}
            </ul>
          ) : null}
          <Link to="/about" className="font-bold">More about {first} →</Link>
        </div>
      </div>
    </section>
  );
}

function ChipIn({ c }) {
  return (
    <section aria-labelledby="chip-h" className="bg-primary text-white">
      <div className="site-container flex flex-wrap items-center justify-between gap-8 py-16">
        <div className="flex max-w-[520px] flex-col gap-3">
          <h2 id="chip-h" className="font-display text-section font-extrabold tracking-[-0.02em]">Chip in for {firstName(c)}</h2>
          <p className="text-[18px] text-white/80">Every shilling pays for agents, transport and posters on the ground.</p>
        </div>
        <div className="flex flex-wrap gap-3" role="group" aria-label="Amount to give">
          {AMOUNTS.map((a) => (
            <Button key={a} asChild variant="accent" size="lg"><Link to={`/contribute?amount=${a}`}>KES {a.toLocaleString("en-KE")}</Link></Button>
          ))}
          <Button asChild variant="onDark" size="lg"><Link to="/contribute">Other</Link></Button>
        </div>
      </div>
    </section>
  );
}

function Engage({ c, onOpen }) {
  return (
    <section className="bg-stone">
      <div className="site-container flex flex-wrap items-stretch gap-5 py-16">
        <div className="flex min-w-0 flex-[2_1_420px] flex-col justify-center gap-3">
          <SectionHead kicker="Get involved" title="Join the team on the ground" />
          <p className="max-w-[56ch] text-text-2">Mobilise your ward, host a baraza or help on polling day. Sign up and the campaign team will call you.</p>
        </div>
        <div className="flex min-w-0 flex-[1_1_300px] flex-col"><SupportCard c={c} onOpen={onOpen} /></div>
      </div>
    </section>
  );
}

export default function AspirantHome() {
  const page = useSiteCandidate();
  const send = useSiteVolunteer();
  const news = usePublicPosts("news").data || [];
  const slides = usePublicSlides().data || [];
  const [volunteering, setVolunteering] = useState(false);
  if (page.isLoading) return <Loading />;
  if (page.error) return <ComingSoon />;
  const c = page.data;
  const open = () => setVolunteering(true);
  const actions = (
    <>
      {c.volunteering_open ? <Button variant="accent" size="lg" onClick={open}>Volunteer for {firstName(c)}</Button> : null}
      <Button asChild variant="onDark" size="lg"><Link to="/contribute">Contribute</Link></Button>
    </>
  );
  return (
    <>
      {slides.length ? <Carousel actions={actions} aside={null} /> : <CandidateHero c={c} actions={actions} />}
      <Ticker news={news} />
      <Why c={c} photo={slides.length > 0} />
      <Agenda limit={6} />
      <ChipIn c={c} />
      <News news={news} />
      <Events />
      {c.volunteering_open ? <Engage c={c} onOpen={open} /> : null}
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
