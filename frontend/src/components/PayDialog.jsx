// Paying by M-Pesa: a prompt sent to the payer's phone, or a Paybill or Till payment the payer
// makes and reports by its code. Used for website contributions and a member's nomination fee.
import { useState } from "react";
import { useContribute, usePayFee, usePayment, usePayOptions } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/input";
import { formatKES } from "../lib/format";
import { ErrorText } from "@/components/ui/error-text";

const AMOUNTS = [200, 500, 1000, 2500, 5000];
const CODE = /^[A-Z0-9]{10}$/;
const PILL = "min-h-11 cursor-pointer rounded-full border-[1.5px] px-4 text-ui font-bold";

function Choice({ active, onClick, children }) {
  return (
    <button type="button" aria-pressed={active} onClick={onClick} className={`${PILL} ${active ? "border-primary bg-primary-tint text-primary" : "border-line-control bg-white text-ink"}`}>
      {children}
    </button>
  );
}

/** Where to pay by hand, and the steps on the phone. */
function PaybillSteps({ options, amount }) {
  const paybill = options.paybill;
  const rows = paybill
    ? [["Paybill", paybill], ["Account", options.account || "Your phone number"], ["Amount", formatKES(amount)]]
    : [["Till", options.till], ["Amount", formatKES(amount)]];
  return (
    <div className="flex flex-col gap-3 rounded-card bg-stone p-4">
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
        {rows.map(([k, v]) => (
          <div key={k} className="contents"><dt className="text-muted-foreground">{k}</dt><dd className="font-display text-[18px] font-extrabold tabular-nums">{v}</dd></div>
        ))}
      </dl>
      <ol className="list-decimal pl-5 text-small leading-[1.6] text-text-2">
        <li>On your phone open M-Pesa, then Lipa na M-Pesa, then {paybill ? "Pay Bill" : "Buy Goods and Services"}.</li>
        <li>Enter the {paybill ? "business and account numbers" : "till number"} and the amount above, then your PIN.</li>
        <li>M-Pesa texts you a confirmation code, like SKL7Q2M9XA. Type it below.</li>
      </ol>
    </div>
  );
}

/** What the payment is doing now: waiting for the phone, paid, waiting for the office, or failed. */
function Status({ reference, onRetry, onDone }) {
  const payment = usePayment(reference);
  const p = payment.data;
  if (!p) return <p className="text-muted-foreground">Checking the payment…</p>;
  if (p.status === "pending") {
    return (
      <div role="status" className="flex flex-col gap-2">
        <p className="font-display text-[20px] font-extrabold">Check your phone</p>
        <p className="text-text-2">Enter your M-Pesa PIN on the prompt to pay {formatKES(p.amount_kes)}. This page updates by itself.</p>
      </div>
    );
  }
  if (p.status === "paid" || p.status === "to_confirm") {
    return (
      <div role="status" className="flex flex-col gap-3">
        <p className="font-display text-[20px] font-extrabold">{p.status === "paid" ? "Thank you, it is paid" : "Thank you, we have your code"}</p>
        <p className="text-text-2">
          {p.status === "paid"
            ? `${formatKES(p.amount_kes)} received.`
            : "The office checks it against the M-Pesa statement and confirms it, usually within a day."}
        </p>
        {p.practice ? <p className="text-small text-muted-foreground">Practice mode: no money moved.</p> : null}
        <Button className="self-start" onClick={onDone}>Done</Button>
      </div>
    );
  }
  return (
    <div role="alert" className="flex flex-col gap-3">
      <p className="font-display text-[20px] font-extrabold">That did not go through</p>
      <p className="text-text-2">{p.reason || "The payment failed. Nothing was taken."}</p>
      <Button className="self-start" onClick={onRetry}>Try again</Button>
    </div>
  );
}

/**
 * `fee` is the fixed nomination fee in KES; without it the dialog takes a contribution of
 * `amount` or any amount the payer picks.
 */
export default function PayDialog({ title, fee, amount: preset, phone: knownPhone = "", onClose }) {
  const options = usePayOptions().data;
  const contribute = useContribute();
  const payFee = usePayFee();
  const send = fee ? payFee : contribute;
  const byHand = !!(options?.paybill || options?.till);
  const [method, setMethod] = useState("stk");
  const [amount, setAmount] = useState(fee || preset || 1000);
  const [f, setF] = useState({ name: "", phone: knownPhone, email: "", code: "" });
  const [reference, setReference] = useState(null);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const code = f.code.trim().toUpperCase();
  const ready =
    amount >= 10 && f.phone.trim().length >= 9 && (fee || f.name.trim().length >= 2) && (method === "stk" || CODE.test(code));
  const submit = (e) => {
    e.preventDefault();
    if (!ready) return;
    const body = { method, phone: f.phone.trim(), ...(method === "manual" ? { mpesa_code: code } : {}) };
    send.mutate(fee ? body : { ...body, amount_kes: Number(amount), name: f.name.trim(), email: f.email.trim() }, {
      onSuccess: (made) => setReference(made.reference),
    });
  };
  const retry = () => { send.reset(); setReference(null); };

  return (
    <Dialog title={title} description={fee ? `Nomination fee: ${formatKES(fee)}` : "Pay by M-Pesa. Every shilling is recorded for the declaration the law requires."} onClose={onClose} className="w-[min(640px,calc(100vw-32px))]">
      {!options ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : reference ? (
        <Status reference={reference} onRetry={retry} onDone={onClose} />
      ) : (
        <form onSubmit={submit} noValidate className="flex flex-col gap-4">
          {!fee ? (
            <fieldset className="flex flex-col gap-2">
              <legend className="mb-2 text-small font-semibold">Amount</legend>
              <div className="flex flex-wrap gap-2">
                {AMOUNTS.map((a) => <Choice key={a} active={Number(amount) === a} onClick={() => setAmount(a)}>{formatKES(a)}</Choice>)}
              </div>
              <Field label="Or another amount (KES)"><Input type="number" min={10} inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} /></Field>
            </fieldset>
          ) : null}
          {byHand ? (
            <div role="group" aria-label="How to pay" className="flex flex-wrap gap-2">
              <Choice active={method === "stk"} onClick={() => setMethod("stk")}>Send a prompt to my phone</Choice>
              <Choice active={method === "manual"} onClick={() => setMethod("manual")}>I paid by {options.paybill ? "Paybill" : "Till"}</Choice>
            </div>
          ) : null}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {!fee ? <Field label="Your name"><Input value={f.name} onChange={set("name")} autoComplete="name" /></Field> : null}
            <Field label="M-Pesa phone number"><Input value={f.phone} onChange={set("phone")} inputMode="tel" autoComplete="tel" placeholder="07XX XXX XXX" /></Field>
            {!fee ? <Field label="Email (optional, for a receipt)"><Input type="email" value={f.email} onChange={set("email")} autoComplete="email" /></Field> : null}
          </div>
          {method === "manual" ? (
            <>
              <PaybillSteps options={options} amount={amount} />
              <Field label="M-Pesa code"><Input value={f.code} onChange={set("code")} maxLength={10} autoCapitalize="characters" placeholder="SKL7Q2M9XA" /></Field>
            </>
          ) : (
            <p className="text-small text-muted-foreground">
              {options.practice ? "Practice mode: no prompt goes out and no money moves." : `You will get an M-Pesa prompt for ${formatKES(amount)}. Enter your PIN to pay.`}
            </p>
          )}
          <ErrorText error={send.error} className="text-small" />
          <Button type="submit" disabled={!ready || send.isPending}>
            {send.isPending ? "Sending…" : method === "manual" ? "Send my code" : `Pay ${formatKES(amount)}`}
          </Button>
        </form>
      )}
    </Dialog>
  );
}
