// An inner page's breadcrumbs and title, as every public page below the home page shows them.
import { Crumbs } from "@/components/ui/typography";

export default function PageHead({ title, lead }) {
  return (
    <div className="flex flex-col gap-3 pb-8">
      <Crumbs items={[{ label: "Home", to: "/" }, { label: title }]} />
      <h1 className="font-display text-page font-extrabold tracking-[-0.03em]">{title}</h1>
      {lead ? <p className="max-w-[680px] text-lead text-muted-foreground">{lead}</p> : null}
    </div>
  );
}

/**
 * The coloured band opening an inner page: breadcrumbs after Home, an optional kicker, the title,
 * an optional lead, then `children`. `tone` is "primary" or "ink".
 */
export function PageHero({ tone = "primary", crumbs, kicker, title, lead, children }) {
  const ink = tone === "ink";
  return (
    <section className={ink ? "bg-ink text-on-dark" : "bg-primary text-white"}>
      <div className="site-container flex flex-col gap-5 py-14">
        <Crumbs onDark items={[{ label: "Home", to: "/" }, ...crumbs]} />
        {kicker ? <p className="text-ui font-bold uppercase tracking-[0.12em] text-accent">{kicker}</p> : null}
        <h1 className="font-display text-page font-extrabold tracking-[-0.03em]">{title}</h1>
        {lead ? <p className={`max-w-[60ch] text-[18px] leading-[1.6] ${ink ? "text-on-dark-muted" : "text-on-primary-muted"}`}>{lead}</p> : null}
        {children}
      </div>
    </section>
  );
}
