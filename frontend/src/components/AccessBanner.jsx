import { useOwnSubscription, useSite } from "../api/hooks";
import { addDays, formatDate } from "../lib/format";
import { HowToPay } from "./CampaignLocked";

const LEADERS = new Set(["candidate", "manager"]);

// The grace or read-only warning above every campaign page; nothing while the campaign is paid.
export default function AccessBanner({ role }) {
  const sub = useOwnSubscription().data;
  const party = useSite().data;
  if (!sub || !["grace_period", "read_only"].includes(sub.state)) return null;
  const leader = LEADERS.has(role);
  const ended = formatDate(sub.paid_until);
  const renew = leader
    ? "Pay the party to renew it."
    : "Your candidate or manager can renew it with the party.";

  if (sub.state === "grace_period") {
    return (
      <div role="status" className="notice-warn">
        The subscription ended on {ended}. Editing stays open until{" "}
        {formatDate(addDays(sub.read_only_from, -1))}; from {formatDate(sub.read_only_from)} the
        campaign is {sub.read_only_from === sub.locks_on ? "locked" : "read-only"}. {renew}
        {leader && <HowToPay instructions={sub.payment_instructions} party={party} className="notice-instructions" />}
      </div>
    );
  }
  return (
    <div role="status" className="notice-bad">
      Read-only since {formatDate(sub.read_only_from)}: the subscription ended on {ended}. Nothing
      can be changed until it is renewed, and the campaign locks on {formatDate(sub.locks_on)}.{" "}
      {renew}
      {leader && <HowToPay instructions={sub.payment_instructions} party={party} className="notice-instructions" />}
    </div>
  );
}
