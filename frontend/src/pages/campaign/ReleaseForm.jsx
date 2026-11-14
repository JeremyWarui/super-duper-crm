import { useState } from "react";
import { usePayoutMode, useReleaseCheck, useReleasePayment } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ErrorText } from "@/components/ui/error-text";
import { FormActions } from "@/components/ui/form-actions";
import { formatKES } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Notice } from "@/components/ui/notice";

// Sends payments one after another and reports how each went.
export default function ReleaseForm({ payments, onClose }) {
  const payout = usePayoutMode();
  const mode = payout.data;
  const release = useReleasePayment();
  const check = useReleaseCheck(payments.map((p) => p.id));
  const cover = check.data;
  const [results, setResults] = useState(null);
  const [running, setRunning] = useState(false);
  const sum = payments.reduce((s, p) => s + p.amount_kes, 0);
  const send = async () => {
    setRunning(true);
    const out = [];
    for (const p of payments) {
      try {
        const done = await release.mutateAsync({ id: p.id });
        out.push({ p, ok: done.status === "paid", pending: done.status === "sending", text: done.status === "paid" ? done.reference : done.failure_reason || done.status });
      } catch (e) {
        out.push({ p, ok: false, text: e.message });
      }
    }
    setResults(out);
    setRunning(false);
  };
  return (
    <Dialog title={payments.length === 1 ? "Release payment" : `Release ${payments.length} payments`} description={`${formatKES(sum)} in total.`} locked={running} onClose={running ? () => {} : onClose}>
      {payout.error && <ErrorText error={`Could not tell whether releases move money: ${payout.error.message}`} />}
      {mode && !mode.moves_money && <Notice className="font-medium">Practice mode: no money moves. Each payment is marked paid under a PRACTICE reference, against a made-up balance.</Notice>}
      <ErrorText error={check.error} />
      {cover && !results && (
        <dl className="flex flex-col gap-2" aria-label="Balance">
          <div className="flex justify-between gap-3"><dt>Payout balance</dt><dd>{formatKES(cover.balance_kes)}</dd></div>
          <div className="flex justify-between gap-3"><dt>These payments</dt><dd>{formatKES(cover.amount_kes)}</dd></div>
          <div className="flex justify-between gap-3"><dt>Transfer fees</dt><dd>{formatKES(cover.fee_kes)}</dd></div>
          <div className={cn("flex justify-between gap-3 font-bold", !cover.enough && "text-bad-foreground")}><dt>Left after</dt><dd>{formatKES(cover.left_kes)}</dd></div>
        </dl>
      )}
      {cover && !results && !cover.enough && <ErrorText error="The balance does not cover these payments and their fees. Add money in the Paystack dashboard, then approve again." />}
      <div className="flex flex-col gap-2">
        {payments.map((p) => {
          const r = results?.find((x) => x.p.id === p.id);
          return (
            <div key={p.id} className="flex flex-wrap justify-between gap-x-3 gap-y-1">
              <span><b>{p.recipient_name}</b> <span className="text-muted-foreground">{p.recipient_phone || "no phone"}</span></span>
              <span>{formatKES(p.amount_kes)}{r && <span className={cn("ml-2 font-semibold", r.ok ? "text-ok-foreground" : r.pending ? "text-warn-foreground" : "text-bad-foreground")}>{r.ok ? `Paid · ${r.text}` : r.pending ? "Sending: Paystack confirms it" : r.text}</span>}</span>
            </div>
          );
        })}
      </div>
      <FormActions>
        {results ? <Button onClick={onClose}>Done</Button> : (
          <>
            <Button variant="quiet" onClick={onClose} disabled={running}>Back</Button>
            <Button loading={running} disabled={!mode || !cover?.enough || running} onClick={send}>{running ? "Sending…" : payments.length === 1 ? "Release" : `Release ${payments.length}`}</Button>
          </>
        )}
      </FormActions>
    </Dialog>
  );
}
