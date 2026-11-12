import { useState } from "react";
import { useSetSignups } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ErrorText } from "@/components/ui/error-text";
import { FormActions } from "@/components/ui/form-actions";
import ShareLink, { QrPrint } from "./ShareLink";
import { linkTo } from "@/lib/format";

export default function QrModal({ event, canClose, onClose }) {
  const setSignups = useSetSignups();
  const link = linkTo(`/join/${event.signup_code}`);
  const [open, setOpen] = useState(event.signups_open);
  const toggle = () => setSignups.mutate({ id: event.id, open: !open }, { onSuccess: () => setOpen(!open) });
  return (
    <Dialog title="Sign-up QR" description={`${event.title || event.ward_name}: people scan it to sign up as supporters.`} onClose={onClose}>
      <QrPrint title={event.title || event.ward_name} link={link} />
      {open && <ShareLink link={link} message={`Sign up as a supporter at ${event.title || event.ward_name}:`} />}
      {!open && <p className="font-semibold text-bad-foreground">Sign-ups are closed: the code shows a "closed" page.</p>}
      <ErrorText error={setSignups.error} />
      <FormActions>
        {canClose && <Button variant="quiet" onClick={toggle} disabled={setSignups.isPending}>{open ? "Close sign-ups" : "Reopen sign-ups"}</Button>}
        <Button variant="quiet" onClick={() => window.print()}>Print</Button>
        <Button onClick={onClose}>Done</Button>
      </FormActions>
    </Dialog>
  );
}
