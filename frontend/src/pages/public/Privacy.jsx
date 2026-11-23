// The site's privacy notice, from its settings.
import { useSite } from "@/api/hooks";
import { Card } from "@/components/ui/card";
import { useCopy } from "@/copy";
import PageHead from "@/components/PageHead";
import { contactOf } from "@/lib/format";

export default function Privacy() {
  const site = useSite().data;
  const copy = useCopy();
  if (!site) return null;
  return (
    <div className="site-container py-12">
      <PageHead title="Privacy notice" lead={`Version ${site.privacy_notice_version}`} />
      <Card className="max-w-[820px]">
        {site.privacy_notice ? (
          <div className="whitespace-pre-line text-base">{site.privacy_notice}</div>
        ) : (
          <p className="text-muted-foreground">{site.name} has not published its privacy notice yet.</p>
        )}
      </Card>
      <section id="data-protection" className="flex max-w-[820px] flex-col gap-2 pt-8">
        <h2 className="font-display text-h3 font-extrabold">Data protection</h2>
        <p className="text-base text-muted-foreground">
          {site.name} holds personal data under the Data Protection Act, 2019. To see, correct or
          delete what it holds about you, contact {copy.owner}
          {contactOf(site) ? ` at ${contactOf(site)}` : ""}
          .
        </p>
      </section>
    </div>
  );
}
