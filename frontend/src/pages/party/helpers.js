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
