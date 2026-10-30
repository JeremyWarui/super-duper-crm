import { Modal } from "../../components/ui";
import { useCancelPayment } from "../../api/hooks";
import { Btn, PrimaryBtn } from "./controls";
import { kes } from "./helpers";

export default function CancelPaymentForm({ payment, onClose }) {
  const cancel = useCancelPayment();
  return (
    <Modal title="Cancel payment" sub={`${kes(payment.amount_kes)} to ${payment.recipient_name}. It stays on the register as cancelled.`} onClose={onClose}>
      {cancel.error && <div className="form-error">{cancel.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Btn onClick={onClose}>Back</Btn>
        <PrimaryBtn disabled={cancel.isPending} onClick={() => cancel.mutate({ id: payment.id }, { onSuccess: onClose })}>Cancel payment</PrimaryBtn>
      </div>
    </Modal>
  );
}

