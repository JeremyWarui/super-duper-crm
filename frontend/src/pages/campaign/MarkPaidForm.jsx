import { useState } from "react";
import { Modal } from "../../components/ui";
import { useMarkPaid } from "../../api/hooks";
import { Btn, Label, PrimaryBtn } from "./controls";
import { kes } from "./helpers";

export default function MarkPaidForm({ payment, onClose }) {
  const markPaid = useMarkPaid();
  const [reference, setReference] = useState("");
  const save = () => markPaid.mutate({ id: payment.id, reference: reference.trim() }, { onSuccess: onClose });
  return (
    <Modal title="Mark paid" sub={`${kes(payment.amount_kes)} to ${payment.recipient_name}. A paid payment cannot be changed.`} onClose={onClose}>
      <Label>M-Pesa or bank reference</Label>
      <input aria-label="Reference" className="app-field" value={reference} onChange={(e) => setReference(e.target.value)} placeholder="QX12AB34" />
      {markPaid.error && <div className="form-error">{markPaid.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Btn onClick={onClose}>Back</Btn>
        <PrimaryBtn disabled={!reference.trim() || markPaid.isPending} onClick={save}>{markPaid.isPending ? "Saving…" : "Mark paid"}</PrimaryBtn>
      </div>
    </Modal>
  );
}

