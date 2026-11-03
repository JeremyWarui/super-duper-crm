// /about: who the party is, what it believes, its leaders, how it is run, and its documents.
import { Link } from "react-router-dom";
import { useParty, usePublicBranches, usePublicDocuments, usePublicIssues, usePublicLeaders } from "@/api/hooks";
import { Card } from "@/components/ui/card";
import { Crumbs } from "@/components/ui/typography";
import { Photo } from "./story";

const ORGANS = [
  ["National Delegates Convention", "Supreme organ; elects national officials and amends the constitution."],
  ["National Executive Committee", "Runs the party between conventions; approves party lists."],
  ["National Elections Board", "Runs nominations and internal elections."],
  ["Appeals & Disputes Committee", "Hears appeals on nominations and party elections."],
];

function Stat({ label, value }) {
  return (
    <Card className="gap-1 p-[18px]">
      <span className="text-small text-muted-foreground">{label}</span>
      <strong className="font-display text-[26px]">{value}</strong>
    </Card>
  );
}

export default function About() {
  const party = useParty().data || {};
  const issues = usePublicIssues().data || [];
  const leaders = usePublicLeaders().data || [];
  const branches = usePublicBranches().data || [];
  const documents = usePublicDocuments().data || [];
  const contact = [party.address, party.contact_phone, party.contact_email].filter(Boolean).join(" · ");
  return (
    <div className="site-container flex flex-col gap-14 pt-14 pb-[72px]">
      <section className="flex flex-wrap items-start gap-10">
        <div className="flex min-w-0 flex-[1_1_520px] flex-col gap-4">
          <Crumbs items={[{ label: "Home", to: "/" }, { label: "About" }]} />
          <p className="text-ui font-bold uppercase tracking-[0.12em] text-primary">About us</p>
          <h1 className="font-display text-[clamp(40px,5vw,64px)] leading-none font-extrabold tracking-[-0.03em]">About {party.short_name || party.name}</h1>
          {party.slogan ? <p className="font-display text-[26px] font-extrabold text-primary">{party.slogan}</p> : null}
          {party.description ? <p className="text-[19px] leading-[1.65] text-text-2">{party.description}</p> : null}
        </div>
        {party.registration_number || branches.length ? (
          <div className="grid min-w-0 flex-[1_1_360px] grid-cols-2 gap-3">
            {party.registration_number ? <Stat label="Registration no." value={party.registration_number} /> : null}
            {branches.length ? <Stat label="County branches" value={branches.length} /> : null}
          </div>
        ) : null}
      </section>

      {issues.length ? (
        <section aria-labelledby="believe-h" className="flex flex-col gap-[18px]">
          <h2 id="believe-h" className="rule-top font-display text-[32px] font-extrabold">What we believe</h2>
          <div className="grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-3.5">
            {issues.map((i) => (
              <div key={i.id} className="flex flex-col gap-2 rounded-[18px] bg-primary-tint p-5">
                <strong className="text-[18px]">{i.title}</strong>
                {i.summary ? <span className="text-[15px] leading-[1.55] text-text-2">{i.summary}</span> : null}
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {leaders.length ? (
        <section aria-labelledby="lead-h" className="flex flex-col gap-[18px]">
          <h2 id="lead-h" className="rule-top font-display text-[32px] font-extrabold">Leadership</h2>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-4">
            {leaders.map((l) => (
              <Card key={l.id} className="gap-0 overflow-hidden p-0">
                <Photo url={l.photo_url} className="aspect-square w-full" />
                <span className="flex flex-col gap-1 p-4">
                  <strong className="text-[17px]">{l.name}</strong>
                  <span className="text-ui text-muted-foreground">{l.position}</span>
                </span>
              </Card>
            ))}
          </div>
        </section>
      ) : null}

      <section className="flex flex-wrap items-stretch gap-6">
        <Card className="min-w-0 flex-[2_1_480px]">
          <h2 className="text-[22px] font-bold">How the party is run</h2>
          {ORGANS.map(([name, what]) => (
            <div key={name} className="flex flex-col gap-0.5 border-t border-line-soft pt-2.5">
              <strong>{name}</strong>
              <span className="text-ui text-muted-foreground">{what}</span>
            </div>
          ))}
        </Card>
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
