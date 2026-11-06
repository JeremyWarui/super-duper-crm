import { useState } from "react";
import { Modal } from "../../components/ui";
import { usePayoutMode, useReleaseCheck, useReleasePayment } from "../../api/hooks";
import { PrimaryBtn, Btn } from "./controls";
import { kes } from "./helpers";

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
    <Modal title={payments.length === 1 ? "Release payment" : `Release ${payments.length} payments`} sub={`${kes(sum)} in total.`} onClose={running ? () => {} : onClose}>
      {payout.error && <div className="form-error">Could not tell whether releases move money: {payout.error.message}</div>}
      {mode && !mode.moves_money && <div className="notice-warn">Practice mode: no money moves. Each payment is marked paid under a PRACTICE reference, against a made-up balance.</div>}
      {check.error && <div className="form-error">{check.error.message}</div>}
      {cover && !results && (
        <dl className="release-list" aria-label="Balance">
          <div className="flex justify-between gap-3"><dt>Payout balance</dt><dd>{kes(cover.balance_kes)}</dd></div>
          <div className="flex justify-between gap-3"><dt>These payments</dt><dd>{kes(cover.amount_kes)}</dd></div>
          <div className="flex justify-between gap-3"><dt>Transfer fees</dt><dd>{kes(cover.fee_kes)}</dd></div>
          <div className={`flex justify-between gap-3 font-bold ${cover.enough ? "" : "text-bad"}`}><dt>Left after</dt><dd>{kes(cover.left_kes)}</dd></div>
          {!cover.enough && <div className="form-error">The balance does not cover these payments and their fees. Add money in the Paystack dashboard, then approve again.</div>}
        </dl>
      )}
      <div className="release-list">
        {payments.map((p) => {
          const r = results?.find((x) => x.p.id === p.id);
          return <div key={p.id} className="flex justify-between gap-3"><span><b>{p.recipient_name}</b> <span className="muted">{p.recipient_phone || "no phone"}</span></span><span>{kes(p.amount_kes)}{r && <span className={`inline-badge ${r.ok ? "text-good" : r.pending ? "text-warn" : "text-bad"}`}>{r.ok ? `Paid · ${r.text}` : r.pending ? "Sending: Paystack confirms it" : r.text}</span>}</span></div>;
        })}
      </div>
      <div className="flex justify-end gap-2 form-actions">
        {results ? <PrimaryBtn onClick={onClose}>Done</PrimaryBtn> : (
          <>
            <Btn onClick={onClose} disabled={running}>Back</Btn>
            <PrimaryBtn disabled={!mode || !cover?.enough || running} onClick={send}>{running ? "Sending…" : payments.length === 1 ? "Release" : `Release ${payments.length}`}</PrimaryBtn>
          </>
        )}
      </div>
    </Modal>
  );
}

