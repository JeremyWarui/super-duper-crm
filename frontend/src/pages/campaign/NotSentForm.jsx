import { Modal } from "../../components/ui";
import { useMarkNotSent } from "../../api/hooks";
import { Btn, PrimaryBtn } from "./controls";
import { kes } from "./helpers";

// After checking the provider: the money did not go, so the payment can be released again.
export default function NotSentForm({ payment, onClose }) {
  const notSent = useMarkNotSent();
  return (
    <Modal title="Didn't go out" sub={`Only if the payout provider shows that ${kes(payment.amount_kes)} to ${payment.recipient_name} was not sent. The payment can then be released again.`} onClose={onClose}>
      {notSent.error && <div className="form-error">{notSent.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Btn onClick={onClose}>Back</Btn>
        <PrimaryBtn disabled={notSent.isPending} onClick={() => notSent.mutate({ id: payment.id }, { onSuccess: onClose })}>It was not sent</PrimaryBtn>
      </div>
    </Modal>
  );
}

