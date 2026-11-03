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
