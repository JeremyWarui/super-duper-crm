// /about: who the party is, what it believes, its leaders, how it is run, and its documents.
import { useRef } from "react";
import { Link } from "react-router-dom";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { usePartyStats, useParty, usePublicDocuments, usePublicLeaders, usePublicOrgans, usePublicValues } from "@/api/hooks";
import { Card } from "@/components/ui/card";
import { Crumbs } from "@/components/ui/typography";
import { Photo } from "./story";

function Stat({ label, value }) {
  return (
    <Card className="gap-1 p-[18px]">
      <span className="text-small text-muted-foreground">{label}</span>
      <strong className="font-display text-[clamp(20px,5vw,26px)] break-words">{value}</strong>
    </Card>
  );
}

/** The leaders in one row that scrolls sideways, by swipe or by the previous and next buttons. */
function LeaderCarousel({ leaders }) {
  const row = useRef(null);
  const move = (dir) => row.current?.scrollBy({ left: dir * row.current.clientWidth * 0.8, behavior: "smooth" });
  const arrow = "flex size-11 cursor-pointer items-center justify-center rounded-full border border-line-control bg-white text-ink hover:bg-stone";
  return (
    <section aria-labelledby="lead-h" className="flex flex-col gap-[18px]">
      <div className="rule-top flex items-center justify-between gap-4">
        <h2 id="lead-h" className="font-display text-[32px] font-extrabold">Leadership</h2>
        <span className="flex gap-2">
          <button type="button" aria-label="Previous leaders" onClick={() => move(-1)} className={arrow}><ChevronLeft className="size-5" /></button>
          <button type="button" aria-label="Next leaders" onClick={() => move(1)} className={arrow}><ChevronRight className="size-5" /></button>
        </span>
      </div>
      <ul ref={row} className="-mx-2 flex snap-x snap-mandatory gap-4 overflow-x-auto px-2 pt-1 pb-6 [scrollbar-width:none]">
        {leaders.map((l) => (
          <li key={l.id} className="w-[min(300px,78vw)] flex-none snap-start">
            <Card className="gap-0 overflow-hidden p-0">
              <Photo url={l.photo_url} className="aspect-square w-full" />
              <span className="flex flex-col gap-1 p-4">
                <strong className="text-[17px]">{l.name}</strong>
                <span className="text-ui text-muted-foreground">{l.position}</span>
              </span>
            </Card>
          </li>
        ))}
      </ul>
      <Link to="/leadership" className="self-start font-bold">Meet the full leadership →</Link>
    </section>
  );
}

export default function About() {
  const party = useParty().data || {};
  const values = usePublicValues().data || [];
  const leaders = usePublicLeaders().data || [];
  const organs = usePublicOrgans().data || [];
  const stats = usePartyStats().data;
  const documents = usePublicDocuments().data || [];
  const tiles = [
    ["Founded", party.founded_year],
    ["Registration no.", party.registration_number],
    ["County branches", stats?.branches],
    ["Members", stats?.members?.toLocaleString("en-KE")],
  ].filter(([, value]) => value);
  const contact = [party.address, party.contact_phone, party.contact_email].filter(Boolean).join(" · ");
  return (
    <div className="site-container flex flex-col gap-14 pt-14 pb-[72px]">
      <section className="flex flex-wrap items-start gap-10">
        <div className="flex min-w-0 flex-[1_1_520px] flex-col gap-4">
          <Crumbs items={[{ label: "Home", to: "/" }, { label: "About" }]} />
          <p className="text-ui font-bold uppercase tracking-[0.12em] text-primary">About us</p>
          <h1 className="font-display text-[clamp(40px,5vw,64px)] leading-none font-extrabold tracking-[-0.03em]">{party.about_headline || `About ${party.short_name || party.name || ""}`}</h1>
          {party.description ? <p className="text-[19px] leading-[1.65] text-text-2">{party.description}</p> : null}
        </div>
        {tiles.length ? (
          <div className="grid min-w-0 flex-[1_1_360px] grid-cols-2 gap-3">
            {tiles.map(([label, value]) => <Stat key={label} label={label} value={value} />)}
          </div>
        ) : null}
      </section>

      {values.length ? (
        <section aria-labelledby="believe-h" className="flex flex-col gap-[18px]">
          <h2 id="believe-h" className="rule-top font-display text-[32px] font-extrabold">What we believe</h2>
          <div className="grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-3.5">
            {values.map((v) => (
              <div key={v.id} className="flex flex-col gap-2 rounded-photo bg-primary-tint p-5">
                <strong className="text-[18px]">{v.title}</strong>
                {v.text ? <span className="text-[15px] leading-[1.55] text-text-2">{v.text}</span> : null}
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {leaders.length ? <LeaderCarousel leaders={leaders} /> : null}

      <section className="flex flex-wrap items-stretch gap-6">
        {organs.length ? (
          <Card className="min-w-0 flex-[2_1_480px]">
            <h2 className="text-[22px] font-bold">How the party is run</h2>
            {organs.map((o) => (
              <div key={o.id} className="flex flex-col gap-0.5 border-t border-line-soft pt-2.5">
                <strong>{o.title}</strong>
                {o.text ? <span className="text-ui text-muted-foreground">{o.text}</span> : null}
              </div>
            ))}
          </Card>
        ) : null}
        <Card variant="ink" className="min-w-0 flex-[1_1_300px]">
          <h2 className="text-[22px] font-bold">Documents</h2>
          {documents.map((d) => (
            <a key={d.id} href={d.url} target="_blank" rel="noreferrer" className="font-bold text-accent hover:text-accent">{d.title}</a>
          ))}
          <Link to="/privacy" className="font-bold text-accent hover:text-accent">Privacy notice</Link>
          {contact ? <span className="text-ui text-on-dark-muted">Headquarters: {contact}</span> : null}
        </Card>
      </section>
    </div>
  );
}
