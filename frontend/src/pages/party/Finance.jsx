// The finance officer's page: campaign subscriptions and their ledger, plans, party payouts, reports and lapse settings.
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  useChoosePlan,
  useCreatePlan,
  useExpiringReport,
  useExtendSubscription,
  useFinancePlans,
  useFinanceSettings,
  useFinanceStateCounts,
  useFinanceSubscription,
  useFinanceSubscriptions,
  useRecordSubscriptionPayment,
  useRevenueReport,
  useSaveFinanceSettings,
  useSetHold,
  useUpdatePlan,
  useVoidEntry,
} from "../../api/hooks";
import {
  Badge,
  Button,
  Chip,
  ErrorState,
  Field,
  LoadingState,
  Modal,
  PageTitle,
  Panel,
} from "../../components/ui";
import { addDays, formatDate, formatKes, formatMonth, formatNumber, nairobiDate } from "../../lib/format";
import {
  ACCESS_LABEL,
  ACCESS_STATES,
  ACCESS_TONE,
  HOLDS,
  RECEIPT_LABEL,
  RECEIPT_METHODS,
  SEAT_LABEL,
  paidUntilAfter,
} from "./helpers";
import Payouts from "./Payouts";

const PAGE_SIZE = 50;
const TABS = [
  ["campaigns", "Campaigns"],
  ["plans", "Plans"],
  ["payouts", "Payouts"],
  ["reports", "Reports"],
  ["settings", "Settings"],
];
const COUNTED = ["", ...ACCESS_STATES.map(([state]) => state)];
const CHASE_DAYS = 14;

const daysFrom = (from, to) => Math.round((Date.parse(to) - Date.parse(from)) / 86_400_000);
const plural = (n, word) => `${formatNumber(n)} ${word}${n === 1 ? "" : "s"}`;
const whole = (text) => /^\d+$/.test(String(text).trim());
// The server's spelling of a reference: compatibility forms folded, no spaces, upper case.
const normalReference = (text) => text.normalize("NFKC").replace(/\s+/g, "").toUpperCase();
const oldest = (today) => addDays(today, -365);
// The server's limits.
const MAX_KES = 10_000_000;
const MAX_DAYS = 730;
const REFERENCE = /^[A-Z0-9/-]{1,40}$/;
const describe = (s) => [s.candidate_name, SEAT_LABEL[s.seat], s.area_name].filter(Boolean).join(" · ");

const Result = ({ tone, children }) => <div className={`result tone-${tone}`}>{children}</div>;

function AccessBadge({ row }) {
  if (row.hold === "suspended") return <Badge text="Suspended" tone="bad" />;
  return <Badge text={ACCESS_LABEL[row.state] || row.state} tone={ACCESS_TONE[row.state]} />;
}

// What happens next to a campaign, in words.
function nextStep(row, today) {
  if (row.state === "grace_period") return `Read-only from ${formatDate(row.read_only_from)}`;
  if (row.state === "read_only") return `Locks on ${formatDate(row.locks_on)}`;
  if (row.state === "active" && row.paid_until) {
    const left = daysFrom(today, row.paid_until);
    return left === 0 ? "Paid period ends today" : `Paid period ends in ${plural(left, "day")}`;
  }
  if (row.state === "pending_payment") return "Never paid; locked until a payment is recorded";
  if (row.hold === "suspended") return "Access stopped by the finance office";
  if (row.state === "locked") return `Locked; the paid period ended ${formatDate(row.paid_until)}`;
  return "—";
}

const URGENT = new Set(["read_only", "locked"]);
const CHASE_SHOWN = 6;

// How long is left on the paid period, or how long ago it ended.
function timeLeft(paidUntil, today) {
  if (!paidUntil) return null;
  const left = daysFrom(today, paidUntil);
  if (left > 0) return [`${plural(left, "day")} left`, left <= CHASE_DAYS ? "text-warn" : "muted"];
  if (left === 0) return ["Ends today", "text-warn"];
  return [`Ended ${plural(-left, "day")} ago`, "text-bad"];
}

// ---- Forms ---------------------------------------------------------------------

function PaymentForm({ subscription, plans, onClose, onDone }) {
  const choosePlan = useChoosePlan();
  const pay = useRecordSubscriptionPayment();
  const today = nairobiDate();
  const [current, setCurrent] = useState(subscription.plan?.id || "");
  const offered = plans.filter((p) => p.active || p.id === current);
  const [planId, setPlanId] = useState(current || (offered.length === 1 ? offered[0].id : ""));
  const [typedAmount, setTypedAmount] = useState(null);
  const [method, setMethod] = useState("mpesa");
  const [reference, setReference] = useState("");
  const [received, setReceived] = useState(today);
  const [note, setNote] = useState("");
  const plan = plans.find((p) => p.id === planId);
  const amount = typedAmount ?? (plan ? String(plan.price_kes) : "");
  const inRange = received >= oldest(today) && received <= today;
  const amountOk = whole(amount) && Number(amount) > 0 && Number(amount) <= MAX_KES;
  const referenceOk = REFERENCE.test(reference);
  const ready = plan && amountOk && referenceOk && inRange;
  const busy = choosePlan.isPending || pay.isPending;
  const error = pay.error || choosePlan.error;
  const until = plan && received ? paidUntilAfter(subscription.paid_until, received, plan.duration_days) : null;

  const save = async () => {
    choosePlan.reset();
    pay.reset();
    try {
      if (planId !== current) {
        await choosePlan.mutateAsync({ id: subscription.id, plan: planId });
        setCurrent(planId);
      }
      const detail = await pay.mutateAsync({
        id: subscription.id,
        amount_kes: Number(amount),
        method,
        reference: reference.trim(),
        received_on: received,
        note: note.trim(),
      });
      onDone(detail, Number(amount));
    } catch {
      // The refusal shows in the form.
    }
  };

  return (
    <Modal
      title="Record payment"
      sub={`${subscription.title} · ${subscription.paid_until ? `paid until ${formatDate(subscription.paid_until)}` : "nothing paid yet"}`}
      onClose={onClose}
    >
      {offered.length === 0 && (
        <>
          <div className="form-error">No plan is offered yet. Create one on the Plans tab first.</div>
          <div className="field-gap" />
        </>
      )}
      <Field label="Plan">
        <select aria-label="Plan" className="app-field" value={planId} disabled={offered.length === 0} onChange={(e) => { setPlanId(e.target.value); setTypedAmount(null); }}>
          <option value="">Choose a plan</option>
          {offered.map((p) => (
            <option key={p.id} value={p.id}>{p.name} · {formatKes(p.price_kes)} for {plural(p.duration_days, "day")}</option>
          ))}
        </select>
      </Field>
      {planId && planId !== current && (
        <div className="field-hint">This also becomes the campaign's plan for later payments.</div>
      )}
      <div className="field-gap" />
      <Field label="Amount received (KES)">
        <input
          aria-label="Amount received (KES)"
          className="app-field"
          inputMode="numeric"
          value={amount}
          onChange={(e) => setTypedAmount(e.target.value.replace(/[,\s]/g, ""))}
        />
      </Field>
      {whole(amount) && Number(amount) > MAX_KES && (
        <div className="field-hint text-bad">A payment is at most {formatKes(MAX_KES)}.</div>
      )}
      {plan && amountOk && Number(amount) !== plan.price_kes && (
        <div className="field-hint text-warn">The plan's price is {formatKes(plan.price_kes)}; the amount is recorded as received.</div>
      )}
      <div className="field-gap" />
      <div className="field-pair">
        <Field label="Method">
          <select aria-label="Method" className="app-field" value={method} onChange={(e) => setMethod(e.target.value)}>
            {RECEIPT_METHODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </Field>
        <Field label="Received on">
          <input aria-label="Received on" type="date" className="app-field" min={oldest(today)} max={today} value={received} onChange={(e) => setReceived(e.target.value)} />
        </Field>
      </div>
      <div className="field-gap" />
      <Field label="Reference">
        <input
          aria-label="Reference"
          className="app-field"
          placeholder="M-Pesa code, bank slip or receipt number"
          maxLength={40}
          value={reference}
          onChange={(e) => setReference(normalReference(e.target.value))}
        />
      </Field>
      {reference && !referenceOk && (
        <div className="field-hint text-bad">Use letters, digits, - and / only.</div>
      )}
      <div className="field-gap" />
      <Field label="Note (optional)">
        <input aria-label="Note" className="app-field" maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} />
      </Field>
      {until && (
        <Result tone="good">
          <div className="result-text">Paid until moves to <span className="strong">{formatDate(until)}</span>.</div>
        </Result>
      )}
      {error && <div className="form-error">{error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Button onClick={onClose}>Cancel</Button>
        <Button primary disabled={!ready || busy} onClick={save}>{busy ? "Recording…" : "Record payment"}</Button>
      </div>
    </Modal>
  );
}

function ExtendForm({ subscription, onClose }) {
  const extend = useExtendSubscription();
  const [days, setDays] = useState("");
  const [note, setNote] = useState("");
  const count = whole(days) ? Number(days) : 0;
  const ready = count >= 1 && count <= 365 && note.trim();
  const save = () =>
    extend.mutate({ id: subscription.id, days: count, note: note.trim() }, { onSuccess: onClose });

  return (
    <Modal title="Extend access" sub={`${subscription.title}. Free days; they are not counted as revenue.`} onClose={onClose}>
      <Field label="Days">
        <input aria-label="Days" className="app-field" inputMode="numeric" placeholder="1 to 365" value={days} onChange={(e) => setDays(e.target.value)} />
      </Field>
      <div className="field-gap" />
      <Field label="Reason">
        <input aria-label="Reason" className="app-field" maxLength={1000} placeholder="Why the campaign gets the days" value={note} onChange={(e) => setNote(e.target.value)} />
      </Field>
      {count >= 1 && count <= 365 && (
        <Result tone="good">
          <div className="result-text">
            Paid until moves to <span className="strong">{formatDate(paidUntilAfter(subscription.paid_until, nairobiDate(), count))}</span>.
          </div>
        </Result>
      )}
      {extend.isError && <div className="form-error">{extend.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Button onClick={onClose}>Cancel</Button>
        <Button primary disabled={!ready || extend.isPending} onClick={save}>{extend.isPending ? "Extending…" : "Extend"}</Button>
      </div>
    </Modal>
  );
}

function HoldForm({ subscription, onClose }) {
  const setHold = useSetHold();
  const [hold, setHoldChoice] = useState("suspended");
  const [reason, setReason] = useState("");
  const save = () =>
    setHold.mutate({ id: subscription.id, hold, reason: reason.trim() }, { onSuccess: onClose });
  const [, verb] = HOLDS.find(([value]) => value === hold);

  return (
    <Modal
      title="Stop access"
      sub={`${subscription.title} is locked while held. Paid days are kept, and lifting the hold restores what the dates give.`}
      onClose={onClose}
    >
      <Field label="Hold">
        <select aria-label="Hold" className="app-field" value={hold} onChange={(e) => setHoldChoice(e.target.value)}>
          {HOLDS.map(([value, , label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </Field>
      <div className="field-gap" />
      <Field label="Reason">
        <input aria-label="Reason" className="app-field" maxLength={1000} placeholder="Why access is stopped" value={reason} onChange={(e) => setReason(e.target.value)} />
      </Field>
      {setHold.isError && <div className="form-error">{setHold.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Button onClick={onClose}>Back</Button>
        <Button tone="danger" disabled={!reason.trim() || setHold.isPending} onClick={save}>
          {setHold.isPending ? "Saving…" : verb}
        </Button>
      </div>
    </Modal>
  );
}

function VoidForm({ subscription, entry, onClose }) {
  const voidEntry = useVoidEntry();
  const [reason, setReason] = useState("");
  const what = entry.kind === "payment"
    ? `the ${formatKes(entry.amount_kes)} payment ${entry.reference}`
    : `the ${plural(entry.days, "day")} extension`;
  const save = () =>
    voidEntry.mutate({ id: subscription.id, entry: entry.id, reason: reason.trim() }, { onSuccess: onClose });

  return (
    <Modal
      title="Void entry"
      sub={`Void ${what}. Paid until goes back to ${entry.paid_until_before ? formatDate(entry.paid_until_before) : "nothing paid"}.`}
      onClose={onClose}
    >
      <Field label="Reason">
        <input aria-label="Reason" className="app-field" maxLength={1000} placeholder="Why the entry is voided" value={reason} onChange={(e) => setReason(e.target.value)} />
      </Field>
      {voidEntry.isError && <div className="form-error">{voidEntry.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Button onClick={onClose}>Back</Button>
        <Button tone="danger" disabled={!reason.trim() || voidEntry.isPending} onClick={save}>
          {voidEntry.isPending ? "Voiding…" : "Void"}
        </Button>
      </div>
    </Modal>
  );
}

// ---- Campaigns tab -------------------------------------------------------------

function Recorded({ done, onOpen }) {
  return (
    <Result tone="good">
      <div className="result-title">{formatKes(done.amount)} recorded for {done.title}</div>
      <div className="result-text">
        Paid until {formatDate(done.paid_until)} · now {ACCESS_LABEL[done.state]}.{" "}
        {onOpen && <button type="button" className="link-button" onClick={onOpen}>Open the ledger</button>}
      </div>
    </Result>
  );
}

function ChasingTable({ rows, today, onOpen, onPay, empty }) {
  return (
    <div className="table-scroll">
      <table className="table">
        <thead>
          <tr><th>Campaign</th><th>State</th><th>Paid until</th><th>Next</th>{onPay && <th />}</tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>
                <button type="button" className="link-button" onClick={() => onOpen(row.id)}>{row.title}</button>
                <div className="cell-sub">{describe(row)}</div>
              </td>
              <td><AccessBadge row={row} /></td>
              <td className="muted">{formatDate(row.paid_until)}</td>
              <td className={URGENT.has(row.state) ? "text-bad" : "text-warn"}>{nextStep(row, today)}</td>
              {onPay && (
                <td className="actions-cell">
                  <Button aria-label={`Record payment for ${row.title}`} onClick={() => onPay(row)}>Record payment</Button>
                </td>
              )}
            </tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={5} className="empty-row">{empty}</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

function CampaignList({ onOpen }) {
  const [state, setState] = useState("");
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [paying, setPaying] = useState(null);
  const [done, setDone] = useState(null);
  const today = nairobiDate();
  const counts = useFinanceStateCounts(COUNTED);
  const list = useFinanceSubscriptions({ state, q: q.trim(), limit: PAGE_SIZE, offset });
  const chasing = useExpiringReport(CHASE_DAYS);
  const lockedRows = useFinanceSubscriptions({ state: "locked", limit: 200 });
  const pendingRows = useFinanceSubscriptions({ state: "pending_payment", limit: 200 });
  const [allChasing, setAllChasing] = useState(false);
  const plans = useFinancePlans();
  const total = list.data?.total ?? 0;
  const items = list.data?.items || [];
  const filter = (next) => { setState(next); setOffset(0); };
  const count = (key) => (counts[key] == null ? "" : ` ${formatNumber(counts[key])}`);
  const chaseError = chasing.error || lockedRows.error || pendingRows.error;
  const chaseReady = chasing.data && lockedRows.data && pendingRows.data;
  const chaseRows = chaseReady
    ? [...chasing.data, ...lockedRows.data.items, ...pendingRows.data.items].filter(
        (row, i, rows) => row.campaign_id && rows.findIndex((r) => r.id === row.id) === i,
      )
    : [];

  return (
    <>
      {done && <Recorded done={done} onOpen={() => onOpen(done.id)} />}
      <Panel pad={0}>
        <div className="card-head">
          <div className="card-title">Needs chasing</div>
          <div className="card-sub">
            Read-only, in grace or ending within {CHASE_DAYS} days, soonest first; then locked and never-paid
            campaigns.
          </div>
        </div>
        {chaseError ? (
          <ErrorState error={chaseError} />
        ) : !chaseReady ? (
          <LoadingState />
        ) : (
          <>
            <ChasingTable
              rows={allChasing ? chaseRows : chaseRows.slice(0, CHASE_SHOWN)}
              today={today}
              onOpen={onOpen}
              onPay={(row) => { setDone(null); setPaying(row); }}
              empty="Nobody to chase: every campaign is paid beyond the next two weeks."
            />
            {(lockedRows.data.total > lockedRows.data.items.length ||
              pendingRows.data.total > pendingRows.data.items.length) && (
              <div className="field-hint">More locked or never-paid campaigns than shown here: use their filters below.</div>
            )}
            {chaseRows.length > CHASE_SHOWN && (
              <div className="flex justify-end chip-row">
                <Button onClick={() => setAllChasing(!allChasing)}>
                  {allChasing ? "Show fewer" : `Show all ${formatNumber(chaseRows.length)}`}
                </Button>
              </div>
            )}
          </>
        )}
      </Panel>
      <div className="field-gap" />
      <div className="flex flex-wrap items-center gap-2 chip-row">
        <input
          aria-label="Search campaigns"
          className="app-field filter-field"
          placeholder="Search by campaign title"
          maxLength={100}
          value={q}
          onChange={(e) => { setQ(e.target.value); setOffset(0); }}
        />
        <Chip on={state === ""} onClick={() => filter("")}>All{count("")}</Chip>
        {ACCESS_STATES.map(([value, label]) => (
          <Chip key={value} on={state === value} onClick={() => filter(value)}>{label}{count(value)}</Chip>
        ))}
      </div>
      {list.error ? (
        <ErrorState error={list.error} />
      ) : list.isLoading ? (
        <LoadingState />
      ) : (
        <>
          <Panel pad={0}>
            <div className="table-scroll">
              <table className="table">
                <thead>
                  <tr><th>Campaign</th><th>Plan</th><th>Paid until</th><th>State</th><th /></tr>
                </thead>
                <tbody>
                  {items.map((row) => (
                    <tr key={row.id}>
                      <td>
                        <button type="button" className="link-button" onClick={() => onOpen(row.id)}>{row.title}</button>
                        <div className="cell-sub">{row.campaign_id ? describe(row) : "Campaign deleted; its ledger is kept"}</div>
                      </td>
                      <td className="muted">{row.plan?.name || "No plan yet"}</td>
                      <td className="muted">
                        {formatDate(row.paid_until)}
                        {timeLeft(row.paid_until, today) && (
                          <div className="cell-sub">
                            <span className={timeLeft(row.paid_until, today)[1]}>{timeLeft(row.paid_until, today)[0]}</span>
                          </div>
                        )}
                      </td>
                      <td><AccessBadge row={row} /></td>
                      <td className="actions-cell">
                        {row.campaign_id && (
                          <Button aria-label={`Record payment for ${row.title}`} onClick={() => { setDone(null); setPaying(row); }}>
                            Record payment
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                  {items.length === 0 && <tr><td colSpan={5} className="empty-row">No campaign matches.</td></tr>}
                </tbody>
              </table>
            </div>
          </Panel>
          <div className="flex items-center justify-between gap-2 chip-row">
            <span className="meta">
              {total === 0 ? "0 campaigns" : `${offset + 1}–${offset + items.length} of ${formatNumber(total)}`}
            </span>
            <div className="flex gap-2">
              <Button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Previous</Button>
              <Button disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>Next</Button>
            </div>
          </div>
        </>
      )}
      {paying && (
        <PaymentForm
          subscription={paying}
          plans={plans.data || []}
          onClose={() => setPaying(null)}
          onDone={(detail, amount) => { setPaying(null); setDone({ ...detail, amount }); }}
        />
      )}
    </>
  );
}

function PlanPicker({ subscription, plans }) {
  const choose = useChoosePlan();
  const current = subscription.plan?.id || "";
  const plan = plans.find((p) => p.id === current);
  const offered = plans.filter((p) => p.active || p.id === current);

  return (
    <Panel>
      <div className="card-title">Plan</div>
      <div className="card-sub">The plan the next payment is for. Past entries keep their own.</div>
      <select
        aria-label="Plan for the next payment"
        className="app-field"
        value={current}
        disabled={choose.isPending || !subscription.campaign_id}
        onChange={(e) => e.target.value && choose.mutate({ id: subscription.id, plan: e.target.value })}
      >
        {!current && <option value="">Choose a plan</option>}
        {offered.map((p) => (
          <option key={p.id} value={p.id}>{p.name}{p.active ? "" : " (no longer offered)"}</option>
        ))}
      </select>
      {plan && <div className="field-hint">{formatKes(plan.price_kes)} for {plural(plan.duration_days, "day")}</div>}
      {offered.length === 0 && <div className="field-hint">No plan is offered yet. Create one on the Plans tab.</div>}
      {choose.isPending && <div className="save-status muted">Saving…</div>}
      {choose.isError && <div className="form-error">{choose.error.message}</div>}
    </Panel>
  );
}

function EntryLine({ entry }) {
  if (entry.kind === "payment") {
    return (
      <>
        <div className="strong">Payment · {RECEIPT_LABEL[entry.method] || entry.method}</div>
        <div className="cell-sub">{[`+${plural(entry.days, "day")}`, entry.reference, entry.plan_name, entry.note].filter(Boolean).join(" · ")}</div>
      </>
    );
  }
  return (
    <>
      <div className="strong">Extension</div>
      <div className="cell-sub">{[`+${plural(entry.days, "day")}`, entry.note].filter(Boolean).join(" · ")}</div>
    </>
  );
}

function Ledger({ subscription, onVoid }) {
  const entries = subscription.entries;
  return (
    <Panel pad={0}>
      <div className="card-head">
        <div className="card-title">Ledger</div>
        <div className="card-sub">Newest first. Only the latest live entry can be voided; to reach an older one, void the newer ones first.</div>
      </div>
      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr><th>Received</th><th>Entry</th><th className="num">Amount</th><th className="num">Days</th><th>Paid until</th><th>Recorded by</th><th /></tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr key={entry.id}>
                <td className="muted">{formatDate(entry.received_on)}</td>
                <td>
                  <EntryLine entry={entry} />
                  {entry.voided_at && (
                    <div className="cell-badge">
                      <Badge text="Voided" tone="neutral" />
                      <span className="cell-sub"> {formatDate(entry.voided_at)}: {entry.void_reason}</span>
                    </div>
                  )}
                </td>
                <td className={`num ${entry.voided_at ? "muted" : "figure"}`}>{entry.amount_kes == null ? "—" : formatKes(entry.amount_kes)}</td>
                <td className="num muted">{entry.days}</td>
                <td className="muted">{formatDate(entry.paid_until_before)} → {formatDate(entry.paid_until_after)}</td>
                <td className="muted">{entry.recorded_by || "—"}</td>
                <td className="actions-cell">
                  {entry.can_void && <Button tone="danger" onClick={() => onVoid(entry)}>Void</Button>}
                </td>
              </tr>
            ))}
            {entries.length === 0 && <tr><td colSpan={7} className="empty-row">Nothing recorded yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function SubscriptionView({ id, onBack }) {
  const detail = useFinanceSubscription(id);
  const plans = useFinancePlans();
  const lift = useSetHold();
  const [modal, setModal] = useState(null);
  const [done, setDone] = useState(null);

  if (detail.isLoading) return <LoadingState />;
  if (detail.error) return <><Button onClick={onBack}>All campaigns</Button><ErrorState error={detail.error} /></>;
  const s = detail.data;
  const open = !!s.campaign_id;
  const held = s.hold !== "none";
  const tiles = [
    ["Access", <AccessBadge key="state" row={s} />],
    ["Paid until", formatDate(s.paid_until)],
    ["Read-only from", formatDate(s.read_only_from)],
    ["Locks on", formatDate(s.locks_on)],
  ];

  return (
    <>
      <div className="chip-row"><Button onClick={onBack}>All campaigns</Button></div>
      <PageTitle
        title={s.title}
        sub={describe(s)}
        action={open && (
          <div className="flex flex-wrap gap-2">
            {held ? (
              <Button disabled={lift.isPending} onClick={() => lift.mutate({ id: s.id, hold: "none" })}>Lift hold</Button>
            ) : (
              <Button tone="danger" onClick={() => setModal({ type: "hold" })}>Stop access</Button>
            )}
            <Button onClick={() => setModal({ type: "extend" })}>Extend</Button>
            <Button primary onClick={() => { setDone(null); setModal({ type: "pay" }); }}>Record payment</Button>
          </div>
        )}
      />
      {!open && <div className="notice-warn">This campaign was deleted. Its ledger is kept for the record and its payments stay in the revenue report.</div>}
      {held && (
        <div className="notice-warn">
          {s.hold === "cancelled" ? "Cancelled" : "Suspended"} by finance: {s.hold_reason}. Lift the hold to restore the access the dates give.
        </div>
      )}
      {lift.isError && <div className="form-error">{lift.error.message}</div>}
      {done && <Recorded done={done} />}
      <div className="kpi-grid">
        {tiles.map(([label, value]) => (
          <Panel key={label} pad={20} className="kpi">
            <div className="kpi-label">{label}</div>
            <div className="kpi-value">{value}</div>
          </Panel>
        ))}
      </div>
      <div className="field-gap" />
      <PlanPicker subscription={s} plans={plans.data || []} />
      <div className="field-gap" />
      <Ledger subscription={s} onVoid={(entry) => setModal({ type: "void", entry })} />
      {modal?.type === "pay" && (
        <PaymentForm
          subscription={s}
          plans={plans.data || []}
          onClose={() => setModal(null)}
          onDone={(next, amount) => { setModal(null); setDone({ ...next, amount }); }}
        />
      )}
      {modal?.type === "extend" && <ExtendForm subscription={s} onClose={() => setModal(null)} />}
      {modal?.type === "hold" && <HoldForm subscription={s} onClose={() => setModal(null)} />}
      {modal?.type === "void" && <VoidForm subscription={s} entry={modal.entry} onClose={() => setModal(null)} />}
    </>
  );
}

// ---- Plans tab -----------------------------------------------------------------

function PlanForm({ plan, onClose }) {
  const create = useCreatePlan();
  const update = useUpdatePlan();
  const write = plan ? update : create;
  const [form, setForm] = useState({
    name: plan?.name || "",
    price_kes: plan ? String(plan.price_kes) : "",
    duration_days: plan ? String(plan.duration_days) : "30",
    description: plan?.description || "",
  });
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const priceOk = whole(form.price_kes) && Number(form.price_kes) <= MAX_KES;
  const daysOk = whole(form.duration_days) && Number(form.duration_days) >= 1 && Number(form.duration_days) <= MAX_DAYS;
  const ready = form.name.trim() && priceOk && daysOk;

  const save = () => {
    const body = {
      name: form.name.trim(),
      price_kes: Number(form.price_kes),
      duration_days: Number(form.duration_days),
      description: form.description.trim(),
    };
    const changed = plan ? Object.fromEntries(Object.entries(body).filter(([key, value]) => value !== plan[key])) : body;
    if (plan && Object.keys(changed).length === 0) return onClose();
    write.mutate(plan ? { id: plan.id, ...changed } : changed, { onSuccess: onClose });
  };

  return (
    <Modal
      title={plan ? `Edit ${plan.name}` : "New plan"}
      sub={plan ? "A change applies to the next payment on this plan; past entries keep what was paid." : "What a campaign pays, and for how many days of access."}
      onClose={onClose}
    >
      <Field label="Name">
        <input aria-label="Plan name" className="app-field" maxLength={80} placeholder="Monthly" value={form.name} onChange={set("name")} />
      </Field>
      <div className="field-gap" />
      <div className="field-pair">
        <Field label="Price (KES)">
          <input aria-label="Price (KES)" className="app-field" inputMode="numeric" value={form.price_kes} onChange={set("price_kes")} />
        </Field>
        <Field label="Days of access">
          <input aria-label="Days of access" className="app-field" inputMode="numeric" value={form.duration_days} onChange={set("duration_days")} />
        </Field>
      </div>
      <div className={`field-hint ${(form.price_kes && !priceOk) || (form.duration_days && !daysOk) ? "text-bad" : ""}`.trim()}>
        Up to {formatKes(MAX_KES)}, for 1 to {formatNumber(MAX_DAYS)} days.
      </div>
      <div className="field-gap" />
      <Field label="Description (optional)">
        <textarea aria-label="Description" className="app-field textarea" maxLength={2000} value={form.description} onChange={set("description")} />
      </Field>
      {write.isError && <div className="form-error">{write.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Button onClick={onClose}>Cancel</Button>
        <Button primary disabled={!ready || write.isPending} onClick={save}>
          {write.isPending ? "Saving…" : plan ? "Save plan" : "Create plan"}
        </Button>
      </div>
    </Modal>
  );
}

function Plans() {
  const plans = useFinancePlans();
  const toggle = useUpdatePlan();
  const [editing, setEditing] = useState(null);

  if (plans.isLoading) return <LoadingState />;
  if (plans.error) return <ErrorState error={plans.error} />;
  const rows = plans.data;
  const live = rows.filter((p) => p.active).length;

  return (
    <>
      <div className="flex items-center justify-between gap-2 chip-row">
        <span className="meta">{plural(rows.length, "plan")} · {formatNumber(live)} offered</span>
        <Button primary onClick={() => setEditing({})}>New plan</Button>
      </div>
      <Panel pad={0}>
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr><th>Plan</th><th className="num">Price</th><th className="num">Days</th><th>Status</th><th /></tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.id}>
                  <td>
                    <div className="strong">{p.name}</div>
                    {p.description && <div className="cell-sub">{p.description}</div>}
                    {toggle.isError && toggle.variables?.id === p.id && <div className="cell-sub text-bad">{toggle.error.message}</div>}
                  </td>
                  <td className="num figure">{formatKes(p.price_kes)}</td>
                  <td className="num">{formatNumber(p.duration_days)}</td>
                  <td><Badge text={p.active ? "Offered" : "Not offered"} tone={p.active ? "good" : "neutral"} /></td>
                  <td className="actions-cell">
                    <div className="flex justify-end gap-2">
                      <Button onClick={() => setEditing(p)}>Edit</Button>
                      <Button
                        disabled={toggle.isPending}
                        onClick={() => toggle.mutate({ id: p.id, active: !p.active })}
                      >
                        {p.active ? "Stop offering" : "Offer again"}
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && <tr><td colSpan={5} className="empty-row">No plans yet. Create one before recording a payment.</td></tr>}
            </tbody>
          </table>
        </div>
      </Panel>
      <div className="page-note">A plan no longer offered stays on the campaigns already on it, and they can still pay for it.</div>
      {editing && <PlanForm plan={editing.id ? editing : null} onClose={() => setEditing(null)} />}
    </>
  );
}

// ---- Reports tab ---------------------------------------------------------------

function ranges(today) {
  const [year, month] = today.split("-").map(Number);
  const pad = (n) => String(n).padStart(2, "0");
  const monthStart = `${year}-${pad(month)}-01`;
  const lastMonthStart = month === 1 ? `${year - 1}-12-01` : `${year}-${pad(month - 1)}-01`;
  return [
    ["This month", monthStart, addDays(month === 12 ? `${year + 1}-01-01` : `${year}-${pad(month + 1)}-01`, -1)],
    ["Last month", lastMonthStart, addDays(monthStart, -1)],
    ["This year", `${year}-01-01`, `${year}-12-31`],
    ["Last year", `${year - 1}-01-01`, `${year - 1}-12-31`],
    ["Last 12 months", addDays(today, -364), today],
  ];
}

function Revenue() {
  const today = nairobiDate();
  const presets = ranges(today);
  const [range, setRange] = useState({ from: presets[2][1], to: presets[2][2] });
  const report = useRevenueReport(range);
  const r = report.data;

  const best = r?.by_month.reduce((a, b) => (b.total_kes > a.total_kes ? b : a), r.by_month[0]);
  const tiles = r && [
    ["Received", formatKes(r.total_kes)],
    ["Payments", formatNumber(r.count)],
    ["Average payment", r.count ? formatKes(Math.round(r.total_kes / r.count)) : "—"],
    ["Best month", best ? formatMonth(best.month) : "—"],
  ];

  return (
    <div className="overview-stack">
      <Panel pad={0}>
        <div className="card-head">
          <div className="card-title">Revenue</div>
          <div className="card-sub">Payments received in the range, both days included. Extensions and voided payments are left out.</div>
          <div className="flex flex-wrap items-center gap-2 chip-row">
            <input aria-label="From" type="date" className="app-field filter-field" value={range.from} onChange={(e) => setRange({ ...range, from: e.target.value })} />
            <span className="muted">to</span>
            <input aria-label="To" type="date" className="app-field filter-field" value={range.to} onChange={(e) => setRange({ ...range, to: e.target.value })} />
            {presets.map(([label, from, to]) => (
              <Chip key={label} on={range.from === from && range.to === to} onClick={() => setRange({ from, to })}>{label}</Chip>
            ))}
          </div>
        </div>
        {report.error && <ErrorState error={report.error} />}
        {!r && !report.error && <LoadingState />}
      </Panel>
      {r && !report.error && (
        <>
          <div className="kpi-grid">
            {tiles.map(([label, value]) => (
              <Panel key={label} pad={20} className="kpi">
                <div className="kpi-label">{label}</div>
                <div className="kpi-value">{value}</div>
              </Panel>
            ))}
          </div>
          <div className="grid overview-grid gap-4">
            <RevenueTable title="By month" head="Month" rows={r.by_month.map((m) => [m.month, formatMonth(m.month), m])} total={r} />
            <RevenueTable title="By plan" head="Plan" rows={r.by_plan.map((p) => [p.plan.id, p.plan.name, p])} total={r} />
          </div>
        </>
      )}
    </div>
  );
}

function RevenueTable({ title, head, rows, total }) {
  return (
    <Panel pad={0}>
      <div className="card-head"><div className="card-title">{title}</div></div>
      <div className="table-scroll">
        <table className="table">
          <thead><tr><th>{head}</th><th className="num">Payments</th><th className="num">Amount</th></tr></thead>
          <tbody>
            {rows.map(([key, label, line]) => (
              <tr key={key}>
                <td>{label}</td>
                <td className="num">{formatNumber(line.count)}</td>
                <td className="num figure">{formatKes(line.total_kes)}</td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={3} className="empty-row">No payments in this range.</td></tr>}
          </tbody>
          <tfoot>
            <tr className="total-row">
              <td className="total-label">TOTAL</td>
              <td className="num">{formatNumber(total.count)}</td>
              <td className="num total-value">{formatKes(total.total_kes)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </Panel>
  );
}

function Expiring({ onOpen }) {
  const [days, setDays] = useState(30);
  const report = useExpiringReport(days);

  return (
    <Panel pad={0}>
      <div className="card-head">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="card-title">Expiring</div>
            <div className="card-sub">Campaigns in grace or read-only, and those whose paid period ends within the window.</div>
          </div>
          <select aria-label="Window" className="app-field filter-field" value={days} onChange={(e) => setDays(Number(e.target.value))}>
            {[7, 14, 30, 60, 90].map((n) => <option key={n} value={n}>Ending within {n} days</option>)}
          </select>
        </div>
      </div>
      {report.error ? (
        <ErrorState error={report.error} />
      ) : !report.data ? (
        <LoadingState />
      ) : (
        <ChasingTable rows={report.data} today={nairobiDate()} onOpen={onOpen} empty={`No campaign lapses or ends within ${days} days.`} />
      )}
    </Panel>
  );
}

// ---- Settings tab --------------------------------------------------------------

function SettingsForm({ settings }) {
  const save = useSaveFinanceSettings();
  const [form, setForm] = useState({
    grace_days: String(settings.grace_days),
    read_only_days: String(settings.read_only_days),
    payment_instructions: settings.payment_instructions,
  });
  const set = (key) => (e) => { setForm({ ...form, [key]: e.target.value }); save.reset(); };
  const inRange = (v) => whole(v) && Number(v) <= 60;
  const ready = inRange(form.grace_days) && inRange(form.read_only_days);
  const grace = Number(form.grace_days);
  const readOnly = Number(form.read_only_days);
  const paid = nairobiDate();
  const readOnlyFrom = addDays(paid, grace + 1);
  const locksOn = addDays(paid, grace + readOnly + 1);

  const submit = () =>
    save.mutate({
      grace_days: grace,
      read_only_days: readOnly,
      payment_instructions: form.payment_instructions.trim(),
    });

  return (
    <Panel>
      <div className="card-title">When an unpaid campaign closes</div>
      <div className="card-sub">After the paid period a campaign keeps full access for the grace days, then can only read for the read-only days, then locks.</div>
      <div className="field-gap" />
      <div className="field-pair">
        <Field label="Grace days (0 to 60)">
          <input aria-label="Grace days" className="app-field" inputMode="numeric" value={form.grace_days} onChange={set("grace_days")} />
        </Field>
        <Field label="Read-only days (0 to 60)">
          <input aria-label="Read-only days" className="app-field" inputMode="numeric" value={form.read_only_days} onChange={set("read_only_days")} />
        </Field>
      </div>
      {ready && (
        <Result tone="warn">
          <div className="result-text">
            A campaign paid until {formatDate(paid)}{" "}
            {readOnly === 0
              ? <>locks on <span className="strong">{formatDate(locksOn)}</span>, with no read-only days.</>
              : <>turns read-only on <span className="strong">{formatDate(readOnlyFrom)}</span> and locks on <span className="strong">{formatDate(locksOn)}</span>.</>}
          </div>
        </Result>
      )}
      <div className="field-gap" />
      <Field label="Payment instructions">
        <textarea
          aria-label="Payment instructions"
          className="app-field textarea"
          maxLength={2000}
          placeholder="Paybill 123456, account: your campaign title. Send the M-Pesa message to the finance office."
          value={form.payment_instructions}
          onChange={set("payment_instructions")}
        />
      </Field>
      <div className="field-hint">Shown to a campaign's team on the payment screen when its access lapses.</div>
      <div className="notice-warn form-actions">Saving moves every campaign's state at once.</div>
      {save.isError && <div className="form-error">{save.error.message}</div>}
      <div className="flex items-center justify-end gap-2">
        {save.isSuccess && <span className="save-status text-good">Saved.</span>}
        <Button primary disabled={!ready || save.isPending} onClick={submit}>{save.isPending ? "Saving…" : "Save settings"}</Button>
      </div>
    </Panel>
  );
}

function Settings() {
  const settings = useFinanceSettings();
  if (settings.isLoading) return <LoadingState />;
  if (settings.error) return <ErrorState error={settings.error} />;
  return <SettingsForm settings={settings.data} />;
}

// ---- Page ----------------------------------------------------------------------

export default function Finance() {
  const [params, setParams] = useSearchParams();
  const tab = TABS.some(([key]) => key === params.get("tab")) ? params.get("tab") : "campaigns";
  const openId = tab === "campaigns" ? params.get("subscription") : null;
  const go = (next) => setParams(next);
  const openSubscription = (id) => go({ tab: "campaigns", subscription: id });

  return (
    <>
      {!openId && <PageTitle title="Finance" sub="Campaign subscriptions and the plans they pay for, and the party's payments to agents and others." />}
      <div className="chip-row">
        <div role="tablist" aria-label="Finance" className="flex gap-1 segmented">
          {TABS.map(([key, label]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={tab === key}
              onClick={() => go({ tab: key })}
              className={`segmented-option ${tab === key ? "segmented-option-on" : ""}`.trim()}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      {tab === "campaigns" && (openId
        ? <SubscriptionView key={openId} id={openId} onBack={() => go({ tab: "campaigns" })} />
        : <CampaignList onOpen={openSubscription} />)}
      {tab === "plans" && <Plans />}
      {tab === "payouts" && <Payouts />}
      {tab === "reports" && (
        <div className="overview-stack">
          <Revenue />
          <Expiring onOpen={openSubscription} />
        </div>
      )}
      {tab === "settings" && <Settings />}
    </>
  );
}
