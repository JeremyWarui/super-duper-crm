// /volunteer: an aspirant installation's volunteer form on its own page.
import { useSiteCandidate, useSiteVolunteer } from "@/api/hooks";
import { SupportForm } from "./Candidate";
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
        <div className="max-w-[620px]">
          <SupportForm c={c} send={send} withdrawPath="/volunteer/withdraw/" />
        </div>
      ) : null}
    </div>
  );
}
