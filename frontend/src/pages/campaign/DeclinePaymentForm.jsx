import { useState } from "react";
import { FormActions, Modal } from "../../components/ui";
import { useDeclinePayment } from "../../api/hooks";
import { Btn, Label, PrimaryBtn } from "./controls";
import { formatKES } from "../../lib/format";

// The approver refuses a payment, saying why; its assignment can be paid by a new one.
export default function DeclinePaymentForm({ payment, onClose }) {
  const decline = useDeclinePayment();
  const [reason, setReason] = useState("");
  return (
    <Modal title="Decline payment" sub={`${formatKES(payment.amount_kes)} to ${payment.recipient_name}. It stays on the register as cancelled, with your reason.`} onClose={onClose}>
      <Label>Reason</Label>
      <input aria-label="Reason" className="app-field" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why it is not paid" />
      {decline.error && <div className="form-error">{decline.error.message}</div>}
      <FormActions>
        <Btn onClick={onClose}>Back</Btn>
        <PrimaryBtn disabled={reason.trim().length < 3 || decline.isPending} onClick={() => decline.mutate({ id: payment.id, reason: reason.trim() }, { onSuccess: onClose })}>Decline payment</PrimaryBtn>
      </FormActions>
    </Modal>
  );
}
