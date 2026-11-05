// An aspirant installation's homepage: the campaign's candidate page and its volunteer form.
import { useSiteCandidate, useSiteVolunteer } from "@/api/hooks";
import { CandidateView } from "./Candidate";
import PageHead from "./PageHead";

export default function AspirantHome() {
  const page = useSiteCandidate();
  const send = useSiteVolunteer();
  if (page.isLoading) return <div className="site-container py-12 text-muted-foreground">Loading…</div>;
  if (page.error) {
    return (
      <div className="site-container py-12">
        <PageHead title="Coming soon" lead="The campaign is preparing this page. Check back shortly." />
      </div>
    );
  }
  return <CandidateView c={page.data} send={send} withdrawPath="/volunteer/withdraw/" />;
}
