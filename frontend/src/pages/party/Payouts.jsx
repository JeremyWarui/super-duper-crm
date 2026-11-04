// The finance officer's payments to agents, volunteers, members and staff, approved by the party
// super admin, and the spend per campaign.
import { useState } from "react";
import {
  useApprovePayout,
  useCancelPayout,
  useMarkPayoutNotSent,
  useMarkPayoutPaid,
  usePartyPayouts,
  usePartyPlaces,
  usePayoutCampaigns,
  usePayoutMode,
  usePayoutPayees,
  usePayoutSpend,
  useReleasePayout,
  useSchedulePayout,
} from "../../api/hooks";
import { Badge, Button, Chip, ErrorState, Field, LoadingState, Modal, Panel } from "../../components/ui";
import { formatDate, formatKes } from "../../lib/format";
import { useAuth } from "../../store/auth";

const KINDS = [
  ["polling_agent", "Polling agent"],
  ["party_agent", "Party agent"],
  ["volunteer", "Volunteer"],
  ["member", "Member"],
  ["staff", "Staff"],
];
const KIND_LABEL = Object.fromEntries(KINDS);
const TONE = { scheduled: "warn", sending: "warn", paid: "good", failed: "bad", cancelled: "neutral" };
const STATUS_LABEL = { scheduled: "Scheduled", sending: "Sending", paid: "Paid", failed: "Failed", cancelled: "Cancelled" };
const OPEN = ["scheduled", "failed"];
const MAX_KES = 1_000_000;

function PlaceSelect({ label, value, places, disabled, onChange }) {
  return (
    <Field label={label}>
      <select aria-label={label} className="app-field" value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
        <option value="">Pick a {label.toLowerCase()}</option>
        {(places || []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
    </Field>
  );
}

// A payee from the member or volunteer register, found by name or phone.
function RegisterPicker({ picked, onPick }) {
  const [q, setQ] = useState("");
  const found = usePayoutPayees(q);
  if (picked) {
    return (
      <div className="flex items-center justify-between gap-2 picked-payee">
        <span><b>{picked.name}</b> <span className="meta">{[picked.phone, picked.polling_station].filter(Boolean).join(" · ")}</span></span>
        <Button onClick={() => onPick(null)}>Change</Button>
      </div>
    );
  }
  return (
    <>
      <Field label="Find a member or volunteer">
        <input aria-label="Find a member or volunteer" className="app-field" placeholder="Name or phone" value={q} onChange={(e) => setQ(e.target.value)} />
      </Field>
      {found.error && <div className="form-error">{found.error.message}</div>}
      {found.data && (
        <ul className="payee-results" aria-label="Matches">
          {found.data.map((p) => (
            <li key={`${p.source}-${p.id}`}>
              <button type="button" className="payee-result" onClick={() => onPick(p)}>
                <b>{p.name}</b> <span className="meta">{p.source === "member" ? "Member" : "Volunteer"} · {p.phone}{p.polling_station ? ` · ${p.polling_station}` : ""}</span>
              </button>
            </li>
          ))}
          {found.data.length === 0 && <li className="meta">Nobody on the registers matches.</li>}
        </ul>
      )}
    </>
  );
}

function ScheduleForm({ onClose }) {
  const schedule = useSchedulePayout();
  const campaigns = usePayoutCampaigns();
  const [kind, setKind] = useState("polling_agent");
  const [byHand, setByHand] = useState(true);
  const [picked, setPicked] = useState(null);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [county, setCounty] = useState("");
  const [constituency, setConstituency] = useState("");
  const [ward, setWard] = useState("");
  const [centre, setCentre] = useState("");
  const [aspirant, setAspirant] = useState("");
  const [purpose, setPurpose] = useState("");
  const [amount, setAmount] = useState("");
  const counties = usePartyPlaces({ enabled: byHand });
  const constituencies = usePartyPlaces({ county, enabled: byHand && !!county });
  const wards = usePartyPlaces({ constituency, enabled: byHand && !!constituency });
  const centres = usePartyPlaces({ ward, enabled: byHand && !!ward });

  const amountOk = /^\d+$/.test(amount.trim()) && Number(amount) >= 1 && Number(amount) <= MAX_KES;
  const payeeOk = byHand ? name.trim() && phone.trim() : !!picked;
  const save = () => {
    const payee = byHand
      ? { name: name.trim(), phone: phone.trim(), centre: centre || null }
      : { [picked.source]: picked.id };
    schedule.mutate(
      { payee_kind: kind, ...payee, aspirant: aspirant || null, purpose: purpose.trim(), amount_kes: Number(amount) },
      { onSuccess: onClose },
    );
  };

  return (
    <Modal title="Schedule payment" sub="Nothing is sent until you release it." onClose={onClose}>
      <Field label="Paying a">
        <select aria-label="Paying a" className="app-field" value={kind} onChange={(e) => setKind(e.target.value)}>
          {KINDS.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
      </Field>
      <div className="field-gap" />
      <div className="flex gap-2 chip-row" role="group" aria-label="Payee from">
        <Chip on={byHand} onClick={() => setByHand(true)}>Type in</Chip>
        <Chip on={!byHand} onClick={() => setByHand(false)}>From the registers</Chip>
      </div>
      {byHand ? (
        <>
          <div className="field-pair">
            <Field label="Name">
              <input aria-label="Name" className="app-field" maxLength={150} value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
            <Field label="M-Pesa phone">
              <input aria-label="M-Pesa phone" className="app-field" inputMode="tel" placeholder="0712 345678" value={phone} onChange={(e) => setPhone(e.target.value)} />
            </Field>
          </div>
          <div className="field-gap" />
          <div className="field-pair">
            <PlaceSelect label="County" value={county} places={counties.data} onChange={(v) => { setCounty(v); setConstituency(""); setWard(""); setCentre(""); }} />
            <PlaceSelect label="Constituency" value={constituency} places={county ? constituencies.data : []} disabled={!county} onChange={(v) => { setConstituency(v); setWard(""); setCentre(""); }} />
          </div>
          <div className="field-pair">
            <PlaceSelect label="Ward" value={ward} places={constituency ? wards.data : []} disabled={!constituency} onChange={(v) => { setWard(v); setCentre(""); }} />
            <PlaceSelect label="Polling station" value={centre} places={ward ? centres.data : []} disabled={!ward} onChange={setCentre} />
          </div>
          <div className="field-hint">The polling station is optional.</div>
        </>
      ) : (
        <RegisterPicker picked={picked} onPick={setPicked} />
      )}
      <div className="field-gap" />
      <Field label="For">
        <select aria-label="For" className="app-field" value={aspirant} onChange={(e) => setAspirant(e.target.value)}>
          <option value="">Party work, no campaign</option>
          {(campaigns.data || []).map((c) => <option key={c.aspirant} value={c.aspirant}>{c.label}</option>)}
        </select>
      </Field>
      <div className="field-gap" />
      <div className="field-pair">
        <Field label="What for (optional)">
          <input aria-label="What for" className="app-field" maxLength={150} placeholder="Polling day" value={purpose} onChange={(e) => setPurpose(e.target.value)} />
        </Field>
        <Field label="Amount (KES)">
          <input aria-label="Amount (KES)" className="app-field" inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </Field>
      </div>
      {amount && !amountOk && <div className="field-hint text-bad">A whole number of shillings, up to {formatKes(MAX_KES)}.</div>}
      {schedule.isError && <div className="form-error">{schedule.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Button onClick={onClose}>Cancel</Button>
        <Button primary disabled={!payeeOk || !amountOk || schedule.isPending} onClick={save}>
          {schedule.isPending ? "Saving…" : "Schedule"}
        </Button>
      </div>
    </Modal>
  );
}

// Sends payments one after another and reports how each went.
function ReleaseForm({ payments, mode, onClose }) {
  const release = useReleasePayout();
  const [results, setResults] = useState(null);
  const [running, setRunning] = useState(false);
  const sum = payments.reduce((s, p) => s + p.amount_kes, 0);
  const send = async () => {
    setRunning(true);
    const out = {};
    for (const p of payments) {
      try {
        const done = await release.mutateAsync({ id: p.id });
        out[p.id] = done.status === "paid"
          ? { tone: "good", text: `Paid · ${done.reference}` }
          : done.status === "sending"
            ? { tone: "warn", text: done.failure_reason || "Sending" }
            : { tone: "bad", text: done.failure_reason || STATUS_LABEL[done.status] };
      } catch (e) {
        out[p.id] = { tone: "bad", text: e.message };
      }
    }
    setResults(out);
    setRunning(false);
  };
  return (
    <Modal title={payments.length === 1 ? "Release payment" : `Release ${payments.length} payments`} sub={`${formatKes(sum)} in total.`} onClose={running ? () => {} : onClose} locked={running}>
      {mode && !mode.moves_money && <div className="notice-warn">Practice mode: no money moves. Each payment is marked paid under a PRACTICE reference.</div>}
      <div className="release-list">
        {payments.map((p) => (
          <div key={p.id} className="flex justify-between gap-3">
            <span><b>{p.recipient_name}</b> <span className="muted">{p.recipient_phone}</span></span>
            <span>{formatKes(p.amount_kes)}{results?.[p.id] && <span className={`inline-badge text-${results[p.id].tone}`}>{results[p.id].text}</span>}</span>
          </div>
        ))}
      </div>
      <div className="flex justify-end gap-2 form-actions">
        {results ? <Button primary onClick={onClose}>Done</Button> : (
          <>
            <Button onClick={onClose} disabled={running}>Back</Button>
            <Button primary disabled={!mode || running} onClick={send}>{running ? "Sending…" : payments.length === 1 ? "Release" : `Release ${payments.length}`}</Button>
          </>
        )}
      </div>
    </Modal>
  );
}

function MarkPaidForm({ payment, onClose }) {
  const markPaid = useMarkPayoutPaid();
  const [reference, setReference] = useState("");
  return (
    <Modal title="Mark paid" sub={`${formatKes(payment.amount_kes)} to ${payment.recipient_name}. A paid payment cannot be changed.`} onClose={onClose}>
      <Field label="M-Pesa or bank reference">
        <input aria-label="Reference" className="app-field" maxLength={50} placeholder="QX12AB34" value={reference} onChange={(e) => setReference(e.target.value)} />
      </Field>
      {markPaid.isError && <div className="form-error">{markPaid.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Button onClick={onClose}>Back</Button>
        <Button primary disabled={!reference.trim() || markPaid.isPending} onClick={() => markPaid.mutate({ id: payment.id, reference: reference.trim() }, { onSuccess: onClose })}>
          {markPaid.isPending ? "Saving…" : "Mark paid"}
        </Button>
      </div>
    </Modal>
  );
}

function ConfirmForm({ title, sub, action, write, payment, onClose }) {
  return (
    <Modal title={title} sub={sub} onClose={onClose}>
      {write.isError && <div className="form-error">{write.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Button onClick={onClose}>Back</Button>
        <Button primary disabled={write.isPending} onClick={() => write.mutate({ id: payment.id }, { onSuccess: onClose })}>{action}</Button>
      </div>
    </Modal>
  );
}

function NotSentForm({ payment, onClose }) {
  return (
    <ConfirmForm
      title="Didn't go out"
      sub={`Only if the payout provider shows that ${formatKes(payment.amount_kes)} to ${payment.recipient_name} was not sent. It can then be released again.`}
      action="It was not sent"
      write={useMarkPayoutNotSent()}
      payment={payment}
      onClose={onClose}
    />
  );
}

function ApproveForm({ payment, onClose }) {
  return (
    <ConfirmForm
      title="Approve payment"
      sub={`${formatKes(payment.amount_kes)} to ${payment.recipient_name}, ${payment.campaign_label || "party work"}${payment.purpose ? `: ${payment.purpose}` : ""}. The finance officer can then release it.`}
      action="Approve"
      write={useApprovePayout()}
      payment={payment}
      onClose={onClose}
    />
  );
}

function CancelForm({ payment, onClose }) {
  return (
    <ConfirmForm
      title="Cancel payment"
      sub={`${formatKes(payment.amount_kes)} to ${payment.recipient_name}. It stays on the register as cancelled.`}
      action="Cancel payment"
      write={useCancelPayout()}
      payment={payment}
      onClose={onClose}
    />
  );
}

function Spend() {
  const spend = usePayoutSpend();
  if (spend.isLoading) return <LoadingState />;
  if (spend.error) return <ErrorState error={spend.error} />;
  const r = spend.data;
  return (
    <Panel pad={0}>
      <div className="card-head"><div className="card-title">Spend by campaign</div></div>
      <div className="table-scroll">
        <table className="table" aria-label="Spend by campaign">
          <thead><tr><th>Campaign</th><th className="num">Paid</th><th className="num">Still owed</th><th className="num">Payments</th></tr></thead>
          <tbody>
            {r.rows.map((row) => (
              <tr key={`${row.aspirant}-${row.label}`}>
                <td>{row.label || "Party work, no campaign"}</td>
                <td className="num figure">{formatKes(row.paid_kes)}</td>
                <td className="num figure">{formatKes(row.owed_kes)}</td>
                <td className="num">{row.payments}</td>
              </tr>
            ))}
            {r.rows.length === 0 && <tr><td colSpan={4} className="empty-row">Nothing spent yet.</td></tr>}
          </tbody>
          {r.rows.length > 0 && (
            <tfoot><tr><th>Total</th><th className="num figure">{formatKes(r.paid_kes)}</th><th className="num figure">{formatKes(r.owed_kes)}</th><th /></tr></tfoot>
          )}
        </table>
      </div>
    </Panel>
  );
}

export default function Payouts() {
  const payouts = usePartyPayouts();
  const payout = usePayoutMode();
  const user = useAuth((s) => s.user);
  const [modal, setModal] = useState(null);
  if (payouts.isLoading) return <LoadingState />;
  if (payouts.error) return <ErrorState error={payouts.error} />;
  const rows = payouts.data;
  const scheduled = rows.filter((p) => p.status === "scheduled" && p.approved_at);
  const waiting = rows.filter((p) => OPEN.includes(p.status) && !p.approved_at);
  // The party super admin approves, never the person who scheduled the payment.
  const mayApprove = (p) => user?.is_superuser && p.created_by !== user.id;
  const total = (statuses) => rows.filter((p) => statuses.includes(p.status)).reduce((s, p) => s + p.amount_kes, 0);
  const close = () => setModal(null);

  return (
    <div className="overview-stack">
      {payout.data && !payout.data.moves_money && (
        <div className="notice-warn">Practice mode: releasing a payment moves no money. Paystack is switched on by the operator when the party's account is ready.</div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="meta">
          {formatKes(total(["paid"]))} paid · {formatKes(total(["scheduled", "sending", "failed"]))} still owed
          {waiting.length > 0 && ` · ${waiting.length} waiting for approval`}
        </span>
        <div className="flex gap-2">
          {scheduled.length > 0 && <Button onClick={() => setModal({ type: "release", payments: scheduled })}>Release all scheduled</Button>}
          <Button primary onClick={() => setModal({ type: "schedule" })}>Schedule payment</Button>
        </div>
      </div>
      <Panel pad={0}>
        <div className="table-scroll">
          <table className="table" aria-label="Party payments">
            <thead><tr><th>Date</th><th>Payee</th><th>For</th><th className="num">Amount</th><th>Status</th><th>Reference</th><th /></tr></thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.id}>
                  <td className="muted">{formatDate(p.paid_at || p.created_at)}</td>
                  <td>
                    <div className="strong">{p.recipient_name}</div>
                    <div className="cell-sub">{[KIND_LABEL[p.payee_kind], p.recipient_phone, p.polling_station].filter(Boolean).join(" · ")}</div>
                  </td>
                  <td>
                    <div>{p.campaign_label || "Party work"}</div>
                    {p.purpose && <div className="cell-sub">{p.purpose}</div>}
                  </td>
                  <td className="num figure">{formatKes(p.amount_kes)}</td>
                  <td>
                    <Badge text={STATUS_LABEL[p.status]} tone={TONE[p.status]} />
                    {OPEN.includes(p.status) && (p.approved_at
                      ? <div className="cell-sub">Approved by {p.approved_by_name}</div>
                      : <div className="cell-sub text-warn">Waiting for approval</div>)}
                    {p.failure_reason && <div className={`cell-sub ${p.status === "failed" ? "text-bad" : "text-warn"}`}>{p.failure_reason}</div>}
                  </td>
                  <td className="muted">{p.reference || "—"}</td>
                  <td className="actions-cell">
                    {OPEN.includes(p.status) && (
                      <div className="flex justify-end gap-2">
                        {p.approved_at ? (
                          <>
                            <Button primary onClick={() => setModal({ type: "release", payments: [p] })}>Release</Button>
                            <Button onClick={() => setModal({ type: "paid", payment: p })}>Mark paid</Button>
                          </>
                        ) : mayApprove(p) && <Button primary onClick={() => setModal({ type: "approve", payment: p })}>Approve</Button>}
                        <Button onClick={() => setModal({ type: "cancel", payment: p })}>Cancel</Button>
                      </div>
                    )}
                    {p.status === "sending" && (p.stuck ? (
                      <div className="flex justify-end gap-2">
                        <Button onClick={() => setModal({ type: "paid", payment: p })}>Mark paid</Button>
                        <Button onClick={() => setModal({ type: "notsent", payment: p })}>Didn't go out</Button>
                      </div>
                    ) : <span className="meta">Waiting for the provider…</span>)}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && <tr><td colSpan={7} className="empty-row">No party payments yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </Panel>
      <Spend />
      {modal?.type === "schedule" && <ScheduleForm onClose={close} />}
      {modal?.type === "release" && <ReleaseForm payments={modal.payments} mode={payout.data} onClose={close} />}
      {modal?.type === "paid" && <MarkPaidForm payment={modal.payment} onClose={close} />}
      {modal?.type === "notsent" && <NotSentForm payment={modal.payment} onClose={close} />}
      {modal?.type === "approve" && <ApproveForm payment={modal.payment} onClose={close} />}
      {modal?.type === "cancel" && <CancelForm payment={modal.payment} onClose={close} />}
    </div>
  );
}
