import { QRCodeSVG } from "qrcode.react";
import { Modal } from "../../components/ui";
import { useCampaignSignups, useSetCampaignSignups } from "../../api/hooks";
import { Btn, ErrorMsg, Loading, PrimaryBtn, ShareLink } from "./controls";

// The campaign-wide sign-up link for posters and messages; the manager opens and closes it.
export default function CampaignLinkModal({ campaign, onClose }) {
  const signups = useCampaignSignups(campaign.id);
  const setSignups = useSetCampaignSignups();
  const sub = "People open it, pick where they vote, and sign up as supporters.";
  if (signups.isLoading) return <Modal title="Campaign sign-up link" sub={sub} onClose={onClose}><Loading /></Modal>;
  if (signups.error) return <Modal title="Campaign sign-up link" sub={sub} onClose={onClose}><ErrorMsg error={signups.error} /></Modal>;
  const { code, open } = signups.data;
  const link = `${window.location.origin}/join/${code}`;
  return (
    <Modal title="Campaign sign-up link" sub={sub} onClose={onClose}>
      <div className="qr-print">
        <div className="qr-title">{campaign.title}</div>
        <QRCodeSVG value={link} size={220} marginSize={2} title={`Sign-up link for ${campaign.title}`} />
        <div className="qr-link">{link}</div>
      </div>
      {open
        ? <ShareLink link={link} message={`Sign up to support ${campaign.title}:`} />
        : <div className="field-hint share-row">The link is closed: anyone who opens it sees a "closed" page. Open it to start taking sign-ups.</div>}
      {setSignups.error && <ErrorMsg error={setSignups.error} />}
      <div className="flex justify-end gap-2 form-actions">
        <Btn onClick={() => setSignups.mutate({ campaign: campaign.id, open: !open })} disabled={setSignups.isPending}>{open ? "Close sign-ups" : "Open sign-ups"}</Btn>
        <Btn onClick={() => window.print()}>Print</Btn>
        <PrimaryBtn onClick={onClose}>Done</PrimaryBtn>
      </div>
    </Modal>
  );
}

