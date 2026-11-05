// /contribute: how to give, from the site settings. The site takes no money itself.
import { useSite } from "@/api/hooks";
import { Card } from "@/components/ui/card";
import { useCopy } from "@/copy";
import PageHead from "./PageHead";

export default function Contribute() {
  const site = useSite().data;
  const copy = useCopy();
  const instructions = site?.payment_instructions?.trim();
  return (
    <div className="site-container py-12">
      <PageHead title="Contribute" lead={copy.contributeLead} />
      <Card variant="elevated" className="max-w-[620px] gap-3 p-8">
        <h2 className="text-[20px] font-bold">How to give</h2>
        {instructions ? (
          <p className="whitespace-pre-line text-base">{instructions}</p>
        ) : (
          <p className="text-muted-foreground">{copy.noInstructions}</p>
        )}
      </Card>
    </div>
  );
}
