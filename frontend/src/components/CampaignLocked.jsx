import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useOwnSubscription, useSite } from "../api/hooks";
import { addDays, formatDate, formatKes } from "../lib/format";
import { useAuth } from "../store/auth";

const LEADERS = new Set(["candidate", "manager"]);

// Why the campaign is locked: only an unpaid or lapsed campaign reopens with a payment.
function causeOf(sub) {
  if (sub.state === "cancelled") return "cancelled";
  if (sub.held) return "held";
  if (!sub.paid_until) return "unpaid";
  return "lapsed";
}

const HEADLINE = {
  cancelled: () => "The party has cancelled this campaign's subscription.",
  held: () => "The party has stopped this campaign's access.",
  unpaid: () => "This campaign has not been paid for yet.",
  lapsed: (sub) => `This campaign's subscription ended on ${formatDate(sub.paid_until)}.`,
};

const REOPENS = {
  cancelled: () => "Ask the party if it can be reopened.",
  held: (sub) => AFTER_THE_STOP[sub.dated_state](sub),
  unpaid: () => "It opens as soon as the party records a payment.",
  lapsed: () => "It opens again as soon as the party records a payment.",
};

// What lifting a hold gives back: exactly what the paid dates allow.
const AFTER_THE_STOP = {
  active: (sub) => `It is paid until ${formatDate(sub.paid_until)} and opens again when the party lifts the stop.`,
  grace_period: (sub) =>
    `The paid period ended on ${formatDate(sub.paid_until)}. Once the party lifts the stop it can be edited until ${formatDate(
      addDays(sub.read_only_from, -1),
    )}; a payment keeps it open.`,
  read_only: (sub) =>
    `The paid period ended on ${formatDate(sub.paid_until)}. Once the party lifts the stop it is read-only and locks on ${formatDate(
      sub.locks_on,
    )}; a payment is due to edit again.`,
  locked: (sub) =>
    `Lifting the stop alone will not reopen it: the paid period ended on ${formatDate(sub.paid_until)}, so a payment is due as well.`,
  pending_payment: () => "Lifting the stop alone will not reopen it: it has not been paid for yet, so a payment is due as well.",
};

const MOBILIZER = {
  cancelled: () => "Your candidate or manager can ask the party about it.",
  held: (sub) =>
    sub.dated_state === "active"
      ? "Your candidate or manager can ask the party about it."
      : "Your candidate or manager can ask the party about it; a payment is due as well.",
  unpaid: () => "Your candidate or manager can pay the party to open it.",
  lapsed: () => "Your candidate or manager can renew it with the party.",
};

// The party's payment instructions, or its contacts when it has written none.
export function HowToPay({ instructions, party, className = "locked-instructions" }) {
  if (instructions.trim()) return <div className={className}>{instructions}</div>;
  const contact = [party?.contact_phone, party?.contact_email].filter(Boolean).join(" · ");
  return <div className={className}>Ask the party's finance office how to pay{contact ? `: ${contact}` : "."}</div>;
}

// A campaign whose subscription allows no access: what happened, what reopens it, and sign out.
export default function CampaignLocked({ message }) {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  const queryClient = useQueryClient();
  const own = useOwnSubscription();
  const party = useSite().data;
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState("");
  const sub = own.data;
  const leader = LEADERS.has(user?.role);
  const cause = sub ? causeOf(sub) : null;
  const payable = cause === "unpaid" || cause === "lapsed" || (cause === "held" && sub.dated_state !== "active");

  // A campaign that has reopened answers the campaigns read, and the gate moves on.
  // Asks the server directly, so a failed check leaves this screen in place rather than an error.
  const checkAgain = async () => {
    setChecking(true);
    setResult("");
    try {
      await api("/campaigns/");
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
    } catch (error) {
      setResult(error.code === "campaign_locked" ? "Still locked." : "Could not check just now; try again.");
    } finally {
      // The banner inside a reopened campaign reads the same subscription, so it must not be stale.
      queryClient.invalidateQueries({ queryKey: ["subscription"] });
      setChecking(false);
    }
  };

  return (
    <div className="gate-no-campaign">
      <div className="gate-no-campaign-card">
        <div className="gate-no-campaign-title">{cause ? HEADLINE[cause](sub) : message}</div>
        {cause && (
          <>
            {leader && sub.hold_reason && (
              <div className="gate-no-campaign-message">The party's reason: {sub.hold_reason}</div>
            )}
            {leader && cause === "cancelled" && sub.paid_until && (
              <div className="gate-no-campaign-message">
                It {sub.dated_state === "active" ? "is" : "was"} paid until {formatDate(sub.paid_until)}.
              </div>
            )}
            <div className="gate-no-campaign-message">{(leader ? REOPENS : MOBILIZER)[cause](sub)}</div>
            {leader && payable && (
              <>
                {sub.plan && (
                  <div className="locked-plan">
                    <span className="strong">{sub.plan.name}</span> · {formatKes(sub.plan.price_kes)} for{" "}
                    {sub.plan.duration_days} days
                  </div>
                )}
                {sub.last_paid_on && (
                  <div className="gate-no-campaign-message">Last payment received {formatDate(sub.last_paid_on)}.</div>
                )}
                <HowToPay instructions={sub.payment_instructions} party={party} />
              </>
            )}
          </>
        )}
        <div className="gate-no-campaign-message">
          You are signed in as {user?.username}. The campaign's data is kept.
        </div>
        <div className="gate-no-campaign-message" role="status">{result}</div>
        <div className="flex gap-2 locked-actions">
          <button type="button" onClick={checkAgain} disabled={checking} className="gate-no-campaign-button">
            {checking ? "Checking…" : "Check again"}
          </button>
          <button type="button" onClick={logout} className="gate-no-campaign-button">
            Sign out
          </button>
        </div>
      </div>
    </div>
  );
}
