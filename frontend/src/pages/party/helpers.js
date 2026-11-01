import { addDays } from "../../lib/format";

export const PARTY_ROLES = [
  ["membership_officer", "Membership Officer"],
  ["nominations_officer", "Nominations Officer"],
  ["finance_officer", "Finance Officer"],
];

export const PARTY_ROLE_LABEL = Object.fromEntries(PARTY_ROLES);

export const STATUS_LABEL = {
  pending: "Pending",
  approved: "Approved",
  suspended: "Suspended",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

export const STATUS_TONE = {
  pending: "warn",
  approved: "good",
  suspended: "warn",
  rejected: "bad",
  withdrawn: "neutral",
};

// The moves an officer offers for each status: [new status, button label].
export const MOVES = {
  pending: [["approved", "Approve"], ["rejected", "Reject"], ["withdrawn", "Withdraw"]],
  approved: [["suspended", "Suspend"], ["withdrawn", "Withdraw"]],
  suspended: [["approved", "Reinstate"], ["withdrawn", "Withdraw"]],
  rejected: [["withdrawn", "Withdraw"]],
  withdrawn: [],
};

export const INTERESTS = [
  ["mobilisation", "Mobilisation"],
  ["events", "Events"],
  ["communications", "Communications"],
  ["social_media", "Social media"],
  ["fundraising", "Fundraising"],
  ["administration", "Administration"],
  ["polling_day", "Polling day"],
];

export const INTEREST_LABEL = Object.fromEntries(INTERESTS);

export const CONTACT_METHODS = [
  ["call", "Call"],
  ["sms", "SMS"],
  ["whatsapp", "WhatsApp"],
  ["email", "Email"],
];

export const CONTACT_LABEL = Object.fromEntries(CONTACT_METHODS);

export const VOLUNTEER_STATUS_LABEL = {
  interested: "Interested",
  active: "Active",
  inactive: "Inactive",
  withdrawn: "Withdrawn",
};

export const VOLUNTEER_STATUS_TONE = {
  interested: "warn",
  active: "good",
  inactive: "neutral",
  withdrawn: "neutral",
};

export const ASPIRANT_STATUS_LABEL = {
  draft: "Draft",
  submitted: "Submitted",
  approved: "Approved",
  suspended: "Suspended",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

export const ASPIRANT_STATUS_TONE = {
  draft: "neutral",
  submitted: "warn",
  approved: "good",
  suspended: "warn",
  rejected: "bad",
  withdrawn: "neutral",
};

// The moves an officer offers for each nomination status: [new status, button label].
export const ASPIRANT_MOVES = {
  draft: [["submitted", "Mark submitted"], ["withdrawn", "Withdraw"]],
  submitted: [["approved", "Approve"], ["rejected", "Reject"], ["withdrawn", "Withdraw"]],
  approved: [["suspended", "Suspend"], ["withdrawn", "Withdraw"]],
  suspended: [["approved", "Reinstate"], ["withdrawn", "Withdraw"]],
  rejected: [],
  withdrawn: [],
};

// Moves the server refuses without a reason.
export const NEEDS_REASON = new Set(["rejected", "suspended"]);

// Each seat and the one area it is fought over.
export const SEATS = [
  ["mca", "MCA", "ward"],
  ["mp", "MP", "constituency"],
  ["governor", "Governor", "county"],
  ["senator", "Senator", "county"],
  ["women_rep", "Women Rep", "county"],
];

export const SEAT_LABEL = Object.fromEntries(SEATS.map(([value, label]) => [value, label]));
export const SEAT_AREA = Object.fromEntries(SEATS.map(([value, , area]) => [value, area]));

// A campaign's access state, its label, and its tone by how urgently it needs chasing.
export const ACCESS_STATES = [
  ["pending_payment", "Pending payment", "warn"],
  ["active", "Active", "good"],
  ["grace_period", "Grace period", "warn"],
  ["read_only", "Read-only", "bad"],
  ["locked", "Locked", "bad"],
  ["cancelled", "Cancelled", "neutral"],
];

export const ACCESS_LABEL = Object.fromEntries(ACCESS_STATES.map(([value, label]) => [value, label]));
export const ACCESS_TONE = Object.fromEntries(ACCESS_STATES.map(([value, , tone]) => [value, tone]));

export const RECEIPT_METHODS = [
  ["mpesa", "M-Pesa"],
  ["bank", "Bank"],
  ["cash", "Cash"],
  ["other", "Other"],
];

export const RECEIPT_LABEL = Object.fromEntries(RECEIPT_METHODS);

export const HOLDS = [
  ["suspended", "Suspend", "Suspended"],
  ["cancelled", "Cancel", "Cancelled"],
];

/** The paid-until date a payment or extension of `days` leaves, received on `received`. */
export function paidUntilAfter(paidUntil, received, days) {
  const next = paidUntil ? addDays(paidUntil, 1) : received;
  const start = next > received ? next : received;
  return addDays(start, days - 1);
}
