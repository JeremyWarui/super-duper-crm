// /issues/:id: one agenda issue, with what will be done and why it matters.
import { Link, NavLink, useParams } from "react-router-dom";
import { usePublicIssue, usePublicIssues } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useCopy } from "@/copy";
import { pageState } from "@/components/PageState";
import { linesOf } from "@/lib/format";
import { PageHero } from "@/components/PageHead";
import { Photo } from "./story";


export default function Issue() {
  const { id } = useParams();
  const issues = usePublicIssues().data || [];
  const issue = usePublicIssue(id);
  const copy = useCopy();
  const state = pageState(issue);
  if (state) return state;
  const i = issue.data;
  const num = issues.findIndex((x) => x.id === i.id) + 1;
  const steps = linesOf(i.what_we_will_do);
  return (
    <>
      {issues.length > 1 ? (
        <div className="border-b border-line-2 bg-white">
          <nav aria-label="Issues" className="site-container flex flex-wrap gap-1">
            {issues.map((x) => (
              <NavLink
                key={x.id}
                to={`/issues/${x.id}`}
                className={({ isActive }) => cn("border-b-[3px] px-3.5 py-3.5 text-body font-semibold no-underline", isActive ? "border-primary text-primary" : "border-transparent text-ink hover:text-primary")}
              >
                {x.title}
              </NavLink>
            ))}
          </nav>
        </div>
      ) : null}
      <PageHero crumbs={[{ label: "Agenda & issues", to: copy.agendaHome }, { label: i.title }]} kicker={<>Our position{num ? ` · issue ${num}` : ""}</>} title={i.title} lead={i.summary} />
      <div className="site-container flex flex-col gap-12 pt-14 pb-[72px]">
        {steps.length || i.image_url ? (
          <section aria-labelledby="w-h" className="grid items-start gap-8 md:grid-cols-2 md:gap-14">
            {i.image_url ? <Photo url={i.image_url} className="aspect-[4/3] w-full rounded-card md:sticky md:top-28" /> : null}
            <div className="reveal-stagger flex min-w-0 flex-col gap-4">
              <h2 id="w-h" className="rule-top font-display text-[36px] font-extrabold">What we will do</h2>
              {steps.map((step, n) => (
                <Card key={n} className="flex-row items-start gap-4 p-[22px]">
                  <span className="flex size-10 flex-none items-center justify-center rounded-full bg-primary-tint font-display text-[20px] font-extrabold text-primary">{n + 1}</span>
                  <span className="text-base">{step}</span>
                </Card>
              ))}
            </div>
          </section>
        ) : null}
        {i.why_it_matters ? (
          <section aria-labelledby="f-h" className="flex flex-col gap-[18px] rounded-panel bg-ink p-8 text-on-dark">
            <h2 id="f-h" className="font-display text-[30px] font-extrabold">Why it matters</h2>
            {linesOf(i.why_it_matters).map((p, n) => <p key={n} className="max-w-[70ch] text-lead text-on-dark-muted">{p}</p>)}
          </section>
        ) : null}
        <section className="flex flex-wrap items-center justify-between gap-4 rounded-card bg-primary-tint p-6">
          <h2 className="text-[22px] font-bold">{copy.issueCta.title}</h2>
          <Button asChild><Link to={copy.issueCta.to}>{copy.issueCta.label}</Link></Button>
        </section>
      </div>
    </>
  );
}
