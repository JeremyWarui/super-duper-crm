// The site's privacy notice, from its settings.
import { useSite } from "@/api/hooks";
import { Card } from "@/components/ui/card";
import { useCopy } from "@/copy";
import PageHead from "./PageHead";

export default function Privacy() {
  const party = useSite().data;
  const copy = useCopy();
  if (!party) return null;
  return (
    <div className="site-container py-12">
      <PageHead title="Privacy notice" lead={`Version ${party.privacy_notice_version}`} />
      <Card className="max-w-[820px]">
        {party.privacy_notice ? (
          <div className="whitespace-pre-line text-base">{party.privacy_notice}</div>
        ) : (
          <p className="text-muted-foreground">{party.name} has not published its privacy notice yet.</p>
        )}
      </Card>
      <section id="data-protection" className="flex max-w-[820px] flex-col gap-2 pt-8">
        <h2 className="font-display text-h3 font-extrabold">Data protection</h2>
        <p className="text-base text-muted-foreground">
          {party.name} holds personal data under the Data Protection Act, 2019. To see, correct or
          delete what it holds about you, contact {copy.organisation}
          {[party.contact_email, party.contact_phone].filter(Boolean).length
            ? ` at ${[party.contact_email, party.contact_phone].filter(Boolean).join(" or ")}`
            : ""}
          .
        </p>
      </section>
    </div>
  );
}
