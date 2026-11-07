// /volunteer: an aspirant installation's volunteer form on its own page, laid out as the dialog.
import { useSiteCandidate, useSiteVolunteer } from "@/api/hooks";
import { Card } from "@/components/ui/card";
import { SupportForm, VOLUNTEER_NOTE, volunteerTitle } from "./Candidate";
import PageHead from "./PageHead";

export default function Volunteer() {
  const page = useSiteCandidate();
  const send = useSiteVolunteer();
  const c = page.data;
  return (
    <div className="site-container py-12">
      <PageHead title="Volunteer" lead={c ? `Help ${c.name} reach every voter in ${c.area}.` : undefined} />
      {page.isLoading ? <p className="text-muted-foreground">Loading…</p> : null}
      {page.error ? <p className="text-muted-foreground">Volunteering opens once the campaign publishes its page.</p> : null}
      {c ? (
        <Card variant="elevated" className="w-full max-w-[760px] gap-4 p-6">
          <div className="flex flex-col gap-1">
            <h2 className="font-display text-h3 font-extrabold">{volunteerTitle(c, send.isSuccess)}</h2>
            {send.isSuccess ? null : <p className="text-ui text-muted-foreground">{VOLUNTEER_NOTE}</p>}
          </div>
          <SupportForm c={c} send={send} withdrawPath="/volunteer/withdraw/" />
        </Card>
      ) : null}
    </div>
  );
}
