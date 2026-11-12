import { useState } from "react";
import { useDeclinePayment } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ErrorText } from "@/components/ui/error-text";
import { FormActions } from "@/components/ui/form-actions";
import { Field, Input } from "@/components/ui/input";
import { formatKES } from "@/lib/format";

// The approver refuses a payment, saying why; its assignment can be paid by a new one.
export default function DeclinePaymentForm({ payment, onClose }) {
  const decline = useDeclinePayment();
  const [reason, setReason] = useState("");
  return (
    <Dialog title="Decline payment" description={`${formatKES(payment.amount_kes)} to ${payment.recipient_name}. It stays on the register as cancelled, with your reason.`} onClose={onClose}>
      <Field label="Reason">
        <Input aria-label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why it is not paid" />
      </Field>
      <ErrorText error={decline.error} />
      <FormActions>
        <Button variant="quiet" onClick={onClose}>Back</Button>
        <Button disabled={reason.trim().length < 3 || decline.isPending} onClick={() => decline.mutate({ id: payment.id, reason: reason.trim() }, { onSuccess: onClose })}>Decline payment</Button>
      </FormActions>
    </Dialog>
  );
}
