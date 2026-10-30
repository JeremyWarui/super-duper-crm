import { useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { Modal } from "../../components/ui";
import { useSetSignups } from "../../api/hooks";
import { Btn, PrimaryBtn, ShareLink } from "./controls";

export default function QrModal({ event, canClose, onClose }) {
  const setSignups = useSetSignups();
  const link = `${window.location.origin}/join/${event.signup_code}`;
  const [open, setOpen] = useState(event.signups_open);
  const toggle = () => setSignups.mutate({ id: event.id, open: !open }, { onSuccess: () => setOpen(!open) });
  return (
    <Modal title="Sign-up QR" sub={`${event.title || event.ward_name}: people scan it to sign up as supporters.`} onClose={onClose}>
      <div className="qr-print">
        <div className="qr-title">{event.title || event.ward_name}</div>
        <QRCodeSVG value={link} size={220} marginSize={2} title={`Sign-up link for ${event.title || event.ward_name}`} />
        <div className="qr-link">{link}</div>
      </div>
      {open && <ShareLink link={link} message={`Sign up as a supporter at ${event.title || event.ward_name}:`} />}
      {!open && <div className="form-error">Sign-ups are closed: the code shows a "closed" page.</div>}
      {setSignups.error && <div className="form-error">{setSignups.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        {canClose && <Btn onClick={toggle} disabled={setSignups.isPending}>{open ? "Close sign-ups" : "Reopen sign-ups"}</Btn>}
        <Btn onClick={() => window.print()}>Print</Btn>
        <PrimaryBtn onClick={onClose}>Done</PrimaryBtn>
      </div>
    </Modal>
  );
}

