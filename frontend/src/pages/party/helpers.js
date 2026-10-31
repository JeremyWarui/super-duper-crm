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
