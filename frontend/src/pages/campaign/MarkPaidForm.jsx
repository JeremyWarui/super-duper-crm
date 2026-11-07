import { useState } from "react";
import { useMarkPaid } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ErrorText } from "@/components/ui/error-text";
import { FormActions } from "@/components/ui/form-actions";
import { Field, Input } from "@/components/ui/input";
import { formatKES } from "@/lib/format";

export default function MarkPaidForm({ payment, onClose }) {
  const markPaid = useMarkPaid();
  const [reference, setReference] = useState("");
  const save = () => markPaid.mutate({ id: payment.id, reference: reference.trim() }, { onSuccess: onClose });
  return (
    <Dialog title="Mark paid" description={`${formatKES(payment.amount_kes)} to ${payment.recipient_name}. A paid payment cannot be changed.`} onClose={onClose}>
      <Field label="M-Pesa or bank reference">
        <Input aria-label="Reference" value={reference} onChange={(e) => setReference(e.target.value)} placeholder="QX12AB34" />
      </Field>
      <ErrorText error={markPaid.error} />
      <FormActions>
        <Button shape="rounded" variant="quiet" onClick={onClose}>Back</Button>
        <Button shape="rounded" disabled={!reference.trim() || markPaid.isPending} onClick={save}>{markPaid.isPending ? "Saving…" : "Mark paid"}</Button>
      </FormActions>
    </Dialog>
  );
}
