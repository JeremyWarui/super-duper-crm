import { useMarkNotSent } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ErrorText } from "@/components/ui/error-text";
import { FormActions } from "@/components/ui/form-actions";
import { formatKES } from "@/lib/format";

// After checking the provider: the money did not go, so the payment can be released again.
export default function NotSentForm({ payment, onClose }) {
  const notSent = useMarkNotSent();
  return (
    <Dialog title="Didn't go out" description={`Only if the payout provider shows that ${formatKES(payment.amount_kes)} to ${payment.recipient_name} was not sent. The payment can then be released again.`} onClose={onClose}>
      <ErrorText error={notSent.error} />
      <FormActions>
        <Button shape="rounded" variant="quiet" onClick={onClose}>Back</Button>
        <Button shape="rounded" disabled={notSent.isPending} onClick={() => notSent.mutate({ id: payment.id }, { onSuccess: onClose })}>It was not sent</Button>
      </FormActions>
    </Dialog>
  );
}
