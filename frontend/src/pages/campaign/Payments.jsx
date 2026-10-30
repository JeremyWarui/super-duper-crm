import { useState } from "react";
import { Badge, PageTitle } from "../../components/ui";
import { usePayments } from "../../api/hooks";
import { Btn, Card, ErrorMsg, Loading } from "./controls";
import { kes } from "./helpers";
import SchedulePaymentForm from "./SchedulePaymentForm";
import MarkPaidForm from "./MarkPaidForm";
import CancelPaymentForm from "./CancelPaymentForm";
import ReleaseForm from "./ReleaseForm";
import NotSentForm from "./NotSentForm";

const PAY_STATUS = { scheduled: "warn", sending: "warn", paid: "good", failed: "bad", cancelled: "neutral" };
const OPEN = ["scheduled", "failed"];  // still to go out: never sent, or a send that failed

// The payments register: the manager schedules, pays and cancels; everyone else reads.
export default function Payments({ campaign, role, mine }) {
  const campaignId = campaign.id;
  const canPay = role === "manager" && !mine;
  const { data, isLoading, error } = usePayments(campaignId);
  const [modal, setModal] = useState(null);
  if (isLoading) return <Loading />; if (error) return <ErrorMsg error={error} />;
  const rows = data || [];
  const total = (status) => rows.filter((p) => p.status === status).reduce((s, p) => s + p.amount_kes, 0);
  const scheduled = rows.filter((p) => p.status === "scheduled");
  const actions = canPay ? (
    <div className="flex gap-2">
      {scheduled.length > 0 && <Btn onClick={() => setModal({ type: "release", payments: scheduled })}>Release all scheduled</Btn>}
      <Btn primary onClick={() => setModal({ type: "schedule" })}>Schedule payment</Btn>
    </div>
  ) : null;
  return (
    <>
      <PageTitle title={mine ? "My payments" : "Payments"} sub={`${kes(total("paid"))} paid · ${kes(total("scheduled"))} scheduled${total("failed") ? ` · ${kes(total("failed"))} failed` : ""}`} action={actions} />
      <Card pad={0}><div className="table-scroll">
        <table className="table">
          <thead><tr>
            <th>Date</th>
            {!mine && <th>Mobilizer</th>}
            <th>Event</th>
            <th className="num">Amount</th>
            <th>Status</th>
            <th>Reference</th>
            {canPay && <th/>}
          </tr></thead>
          <tbody>{rows.map((p) => (
            <tr key={p.id}>
              <td className="muted">{new Date(p.paid_at || p.created_at).toLocaleDateString()}</td>
              {!mine && <td><div className="strong">{p.recipient_name}</div><div className="meta">{p.recipient_phone || "—"}</div></td>}
              <td>{p.event_title || "—"}</td>
              <td className="num figure">{kes(p.amount_kes)}</td>
              <td><Badge text={p.status} tone={PAY_STATUS[p.status]} />{p.failure_reason && (canPay || p.status === "failed") && <div className={`failure-reason ${p.status === "failed" ? "text-bad" : "text-warn"}`}>{p.failure_reason}</div>}</td>
              <td className="muted">{p.reference || "—"}</td>
              {canPay && <td className="actions-cell">{OPEN.includes(p.status) && <div className="flex justify-end gap-2"><Btn primary onClick={() => setModal({ type: "release", payments: [p] })}>Release</Btn><Btn onClick={() => setModal({ type: "paid", payment: p })}>Mark paid</Btn><Btn onClick={() => setModal({ type: "cancel", payment: p })}>Cancel</Btn></div>}{p.status === "sending" && (p.stuck
                ? <div className="flex justify-end gap-2"><Btn onClick={() => setModal({ type: "paid", payment: p })}>Mark paid</Btn><Btn onClick={() => setModal({ type: "notsent", payment: p })}>Didn't go out</Btn></div>
                : <span className="meta">Waiting for the provider…</span>)}</td>}
            </tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={7} className="empty-row">No payments yet.</td></tr>}</tbody>
        </table>
      </div></Card>
      {modal?.type === "schedule" && <SchedulePaymentForm campaignId={campaignId} onClose={() => setModal(null)} />}
      {modal?.type === "paid" && <MarkPaidForm payment={modal.payment} onClose={() => setModal(null)} />}
      {modal?.type === "cancel" && <CancelPaymentForm payment={modal.payment} onClose={() => setModal(null)} />}
      {modal?.type === "release" && <ReleaseForm payments={modal.payments} onClose={() => setModal(null)} />}
      {modal?.type === "notsent" && <NotSentForm payment={modal.payment} onClose={() => setModal(null)} />}
    </>
  );
}

