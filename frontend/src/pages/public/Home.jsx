// The campaign website's homepage, and its About, Agenda and Media pages.
import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Check, FileText } from "lucide-react";
import { usePublicDocuments, usePublicIssues, usePublicPosts, usePublicVideos, useSiteCandidate, useSiteVolunteer } from "@/api/hooks";
import { paragraphs } from "@/components/RichTextView";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Reveal } from "@/components/ui/reveal";
import { SectionHead } from "@/components/ui/typography";
import { CandidateView, VolunteerDialog, vying } from "./Candidate";
import { Agenda, Carousel, Events, News, TakePart, Ticker } from "./sections";
import PageHead from "@/components/PageHead";
import { Photo, QuickLinks, VideoCard } from "./story";
import { pageState } from "@/components/PageState";
import { firstName, linesOf } from "@/lib/format";
import { usePageTitle } from "@/lib/title";

const WITHDRAW = "/volunteer/withdraw/";

function ComingSoon() {
  return (
    <div className="site-container py-12">
      <PageHead title="Coming soon" lead="The campaign is preparing this page. Check back shortly." />
    </div>
  );
}

/** Beside the carousel: who is standing, and quick links. */
function CandidateCard({ c }) {
  return (
    <div className="hero-card flex flex-[0_1_360px] flex-col gap-3.5 rounded-[13px] bg-white p-6 text-ink shadow-hero-card">
      <div className="flex items-center gap-3.5">
        <Photo url={c.photo_url} alt={c.name} className="size-[72px] flex-none rounded-full bg-primary-tint" />
        <span className="flex flex-col gap-0.5">
          <h2 className="font-display text-[22px] leading-tight font-extrabold">{c.name}</h2>
          <span className="text-ui text-muted-foreground">{vying(c.seat)} · {c.area}</span>
        </span>
      </div>
      <QuickLinks links={[["About " + firstName(c.name), "/about"], ["The agenda", "/agenda"], ["Events near me", "/events"], ["Contribute", "/contribute"]]} />
    </div>
  );
}

/** Why the candidate: photo, the bio's first paragraph and the priorities. */
function Candidate({ c }) {
  const first = firstName(c.name);
  const [lead] = paragraphs(c.bio);
  return (
    <section id="about" className="bg-primary text-white">
      <div className="site-container flex flex-col gap-7 py-12 sm:py-[72px]">
        <SectionHead kicker="Who is standing" title={`Why ${first}?`} action={{ label: `More about ${first}`, to: "/about" }} onDark />
        <div className="reveal-stagger flex flex-wrap items-center gap-8">
          {c.photo_url ? <img src={c.photo_url} alt={c.name} className="size-[120px] flex-none rounded-full border-2 border-accent object-cover" /> : <span className="size-[120px] flex-none rounded-full border-2 border-accent bg-white/20" />}
          <div className="flex min-w-0 flex-[1_1_420px] flex-col gap-3">
            {lead ? <p className="max-w-[68ch] text-[18px] leading-[1.7] text-on-primary-muted">{lead}</p> : null}
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

export default function Home() {
  const page = useSiteCandidate();
  const send = useSiteVolunteer();
  const news = usePublicPosts("news").data || [];
  const [volunteering, setVolunteering] = useState(false);
  if (page.isLoading) return pageState(page);
  if (page.error) return <ComingSoon />;
  const c = page.data;
  const first = firstName(c.name);
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
      <h1 className="sr-only">{c.name}: {vying(c.seat)}, {c.area}</h1>
      <Carousel fallback={{ id: "candidate", kicker: c.name, headline: c.slogan || c.name, line: "", image_url: "" }} actions={volunteer} aside={<CandidateCard c={c} />} />
      <Ticker news={news} />
      <Reveal><Agenda limit={6} /></Reveal>
      <Reveal><News news={news} /></Reveal>
      <Reveal><Events /></Reveal>
      <Reveal><Candidate c={c} /></Reveal>
      <Reveal><TakePart panels={panels} /></Reveal>
      {volunteering ? <VolunteerDialog c={c} send={send} withdrawPath={WITHDRAW} onClose={() => setVolunteering(false)} /> : null}
    </>
  );
}

/** /about: the candidate's full profile. */
export function About() {
  const page = useSiteCandidate();
  const send = useSiteVolunteer();
  usePageTitle(page.data ? `About ${page.data.name}` : "About");
  if (page.isLoading) return pageState(page);
  if (page.error) return <ComingSoon />;
  return <CandidateView c={page.data} send={send} withdrawPath={WITHDRAW} crumbs={[{ label: "Home", to: "/" }, { label: "About" }]} />;
}

/** One agenda issue as a row: its photo on one side, what the campaign will do on the other. */
function IssueRow({ issue, n }) {
  const steps = linesOf(issue.what_we_will_do).slice(0, 3);
  const flip = n % 2 === 1;
  return (
    <article aria-labelledby={`issue-${issue.id}`} className="grid items-center gap-8 md:grid-cols-2 md:gap-14">
      <Link to={`/issues/${issue.id}`} aria-hidden tabIndex={-1} className={`group relative block overflow-hidden rounded-card ${flip ? "md:order-2" : ""}`}>
        <Photo url={issue.image_url} className="aspect-[4/3] w-full transition-transform duration-700 group-hover:scale-[1.04]" />
        <span className="absolute top-4 left-4 flex size-12 items-center justify-center rounded-full bg-accent font-display text-[20px] font-extrabold text-ink">{n + 1}</span>
      </Link>
      <div className="reveal-stagger flex min-w-0 flex-col gap-4">
        <p className="kicker">Issue {n + 1}</p>
        <h2 id={`issue-${issue.id}`} className="font-display text-[clamp(28px,3.2vw,40px)] leading-[1.1] font-extrabold tracking-[-0.02em]">{issue.title}</h2>
        {issue.summary ? <p className="text-lead text-text-2">{issue.summary}</p> : null}
        {steps.length ? (
          <ul className="flex flex-col gap-2.5">
            {steps.map((step, k) => (
              <li key={k} className="flex gap-3 text-body">
                <Check className="mt-0.5 size-5 flex-none text-primary" strokeWidth={3} aria-hidden />
                <span>{step}</span>
              </li>
            ))}
          </ul>
        ) : null}
        <div>
          <Button asChild variant="outline"><Link to={`/issues/${issue.id}`}>Our full position on {issue.title.toLowerCase()} <ArrowRight className="size-4" aria-hidden /></Link></Button>
        </div>
      </div>
    </article>
  );
}

/** /agenda: every published agenda issue, one row each with photos on alternate sides. */
export function AgendaPage() {
  const issues = usePublicIssues();
  return (
    <div className="site-container flex flex-col gap-10 sm:gap-16 pt-8 sm:pt-12 pb-14 sm:pb-24 md:gap-24">
      <PageHead title="Agenda" lead="Where the campaign stands, issue by issue." />
      {issues.isSuccess && !issues.data.length ? <p className="text-muted-foreground">The agenda is not published yet.</p> : null}
      {(issues.data || []).map((issue, n) => <Reveal key={issue.id}><IssueRow issue={issue} n={n} /></Reveal>)}
    </div>
  );
}

/** /media: every published video and document. */
export function Media() {
  const videos = usePublicVideos().data || [];
  const documents = usePublicDocuments().data || [];
  return (
    <div className="site-container flex flex-col gap-12 pt-8 sm:pt-12 pb-12 sm:pb-20">
      <PageHead title="Videos & documents" lead="Speeches, interviews and the campaign's own papers." />
      {videos.length ? (
        <Reveal><section aria-labelledby="videos-h" className="flex flex-col gap-4">
          <h2 id="videos-h" className="rule-top font-display text-[28px] font-extrabold">Videos</h2>
          <div className="reveal-stagger grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-5">
            {videos.map((v) => <VideoCard key={v.id} video={v} />)}
          </div>
        </section></Reveal>
      ) : null}
      {documents.length ? (
        <Reveal><section aria-labelledby="docs-h" className="flex flex-col gap-4">
          <h2 id="docs-h" className="rule-top font-display text-[28px] font-extrabold">Documents</h2>
          <div className="reveal-stagger grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-3">
            {documents.map((d) => (
              <Card key={d.id} asChild interactive className="flex-row items-center gap-3 p-4">
                <a href={d.url} target="_blank" rel="noreferrer" className="text-ink no-underline"><FileText aria-hidden className="size-5 flex-none text-primary" /><span className="font-bold">{d.title}</span></a>
              </Card>
            ))}
          </div>
        </section></Reveal>
      ) : null}
      {!videos.length && !documents.length ? <p className="text-muted-foreground">Nothing published here yet.</p> : null}
    </div>
  );
}
