// /issues/:id: one agenda issue, with what will be done and why it matters.
import { Link, NavLink, useParams } from "react-router-dom";
import { usePublicIssue, usePublicIssues } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Crumbs } from "@/components/ui/typography";
import { cn } from "@/lib/utils";
import { useCopy } from "@/copy";

const lines = (text) => text.split("\n").map((l) => l.trim()).filter(Boolean);

export default function Issue() {
  const { id } = useParams();
  const issues = usePublicIssues().data || [];
  const issue = usePublicIssue(id);
  const copy = useCopy();
  if (issue.isLoading) return <div className="site-container py-12 text-muted-foreground">Loading…</div>;
  if (issue.error) return <div role="alert" className="site-container py-12">{issue.error.message}</div>;
  const i = issue.data;
  const num = issues.findIndex((x) => x.id === i.id) + 1;
  const steps = lines(i.what_we_will_do);
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
      <section className="bg-primary text-white">
        <div className="site-container flex flex-col gap-4 py-14">
          <Crumbs onDark items={[{ label: "Home", to: "/" }, { label: "Agenda & issues", to: copy.agendaHome }, { label: i.title }]} />
          <p className="text-ui font-bold uppercase tracking-[0.12em] text-accent">Our position{num ? ` · issue ${num}` : ""}</p>
          <h1 className="font-display text-page font-extrabold tracking-[-0.03em]">{i.title}</h1>
          {i.summary ? <p className="max-w-[46ch] text-[19px] leading-[1.6] text-[#CFE0D5]">{i.summary}</p> : null}
        </div>
      </section>
      <div className="site-container flex flex-col gap-12 pt-14 pb-[72px]">
        {steps.length ? (
          <section aria-labelledby="w-h" className="flex flex-col gap-5">
            <h2 id="w-h" className="rule-top font-display text-[36px] font-extrabold">What we will do</h2>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-4">
              {steps.map((step, n) => (
                <Card key={n} className="p-[22px]">
                  <span className="font-display text-[28px] font-extrabold text-primary">{n + 1}</span>
                  <span className="text-base">{step}</span>
                </Card>
              ))}
            </div>
          </section>
        ) : null}
        {i.why_it_matters ? (
          <section aria-labelledby="f-h" className="flex flex-col gap-[18px] rounded-panel bg-ink p-8 text-on-dark">
            <h2 id="f-h" className="font-display text-[30px] font-extrabold">Why it matters</h2>
            {lines(i.why_it_matters).map((p, n) => <p key={n} className="max-w-[70ch] text-lead text-on-dark-muted">{p}</p>)}
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
