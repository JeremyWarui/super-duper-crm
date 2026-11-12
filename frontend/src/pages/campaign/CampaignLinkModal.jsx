import { useCampaignSignups, useSetCampaignSignups } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ErrorText } from "@/components/ui/error-text";
import { FormActions } from "@/components/ui/form-actions";
import { LoadingText } from "@/components/ui/loading-text";
import ShareLink, { QrPrint } from "./ShareLink";
import { linkTo } from "@/lib/format";

// The campaign-wide sign-up link for posters and messages; the manager opens and closes it.
export default function CampaignLinkModal({ campaign, onClose }) {
  const signups = useCampaignSignups(campaign.id);
  const setSignups = useSetCampaignSignups();
  const sub = "People open it, pick where they vote, and sign up as supporters.";
  if (signups.isLoading) return <Dialog title="Campaign sign-up link" description={sub} onClose={onClose}><LoadingText /></Dialog>;
  if (signups.error) return <Dialog title="Campaign sign-up link" description={sub} onClose={onClose}><ErrorText error={signups.error} /></Dialog>;
  const { code, open } = signups.data;
  const link = linkTo(`/join/${code}`);
  return (
    <Dialog title="Campaign sign-up link" description={sub} onClose={onClose}>
      <QrPrint title={campaign.title} link={link} />
      {open
        ? <ShareLink link={link} message={`Sign up to support ${campaign.title}:`} />
        : <p className="text-small text-muted-foreground">The link is closed: anyone who opens it sees a "closed" page. Open it to start taking sign-ups.</p>}
      <ErrorText error={setSignups.error} />
      <FormActions>
        <Button variant="quiet" onClick={() => setSignups.mutate({ campaign: campaign.id, open: !open })} disabled={setSignups.isPending}>{open ? "Close sign-ups" : "Open sign-ups"}</Button>
        <Button variant="quiet" onClick={() => window.print()}>Print</Button>
        <Button onClick={onClose}>Done</Button>
      </FormActions>
    </Dialog>
  );
}
