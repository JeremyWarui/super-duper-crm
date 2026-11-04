// /manifesto: the manifesto's commitments, one per line, the agenda issues, and the full document.
import { Link } from "react-router-dom";
import { useSite, usePublicIssues } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Crumbs } from "@/components/ui/typography";

const commitments = (text) =>
  text.split("\n").map((l) => l.trim().replace(/^\d+[.)]\s*/, "")).filter(Boolean);

export default function Manifesto() {
  const party = useSite().data || {};
  const issues = usePublicIssues().data || [];
  const lines = commitments(party.manifesto_text || "");
  return (
    <>
      <section className="bg-ink text-on-dark">
        <div className="site-container flex flex-col gap-5 py-14">
          <Crumbs onDark items={[{ label: "Home", to: "/" }, { label: "Manifesto" }]} />
          <p className="text-ui font-bold uppercase tracking-[0.12em] text-accent">Our plan for Kenya</p>
          <h1 className="font-display text-[clamp(40px,5vw,64px)] leading-none font-extrabold tracking-[-0.03em]">Manifesto</h1>
          {party.slogan ? <p className="font-display text-[24px] font-extrabold text-accent">{party.slogan}</p> : null}
          {party.manifesto_url ? (
            <Button asChild variant="accent" className="self-start">
              <a href={party.manifesto_url} target="_blank" rel="noreferrer">Read the full manifesto</a>
            </Button>
          ) : null}
        </div>
      </section>
      <div className="site-container flex flex-col gap-12 pt-14 pb-[72px]">
        <section aria-labelledby="commit-h" className="flex flex-col gap-5">
          <h2 id="commit-h" className="rule-top font-display text-[32px] font-extrabold">What we commit to</h2>
          {lines.length ? (
            <ol className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
              {lines.map((line, n) => (
                <Card key={n} asChild className="p-[22px]">
                  <li>
                    <span className="font-display text-[28px] font-extrabold text-primary">{n + 1}</span>
                    <span className="text-[17px] leading-[1.55]">{line}</span>
                  </li>
                </Card>
              ))}
            </ol>
          ) : (
            <p className="text-muted-foreground">The manifesto will be published here.</p>
          )}
        </section>
        {issues.length ? (
          <section aria-labelledby="issues-h" className="flex flex-col gap-5">
            <h2 id="issues-h" className="rule-top font-display text-[32px] font-extrabold">Our positions</h2>
            <div className="grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-4">
              {issues.map((i) => (
                <Card key={i.id} asChild interactive className="p-[22px]">
                  <Link to={`/issues/${i.id}`}>
                    <strong className="text-[18px]">{i.title}</strong>
                    {i.summary ? <span className="text-ui text-text-2">{i.summary}</span> : null}
                    <span className="text-ui font-bold text-primary">Our position →</span>
                  </Link>
                </Card>
              ))}
            </div>
          </section>
        ) : null}
        <Card variant="panel" className="flex-row flex-wrap items-center justify-between gap-6 bg-primary-tint">
          <span className="flex flex-col gap-1.5">
            <strong className="font-display text-[26px] font-extrabold">Help us deliver it</strong>
            <span className="text-text-2">Join the party and have a say in your branch.</span>
          </span>
          <Button asChild><Link to="/join-party">Join the party</Link></Button>
        </Card>
      </div>
    </>
  );
}
