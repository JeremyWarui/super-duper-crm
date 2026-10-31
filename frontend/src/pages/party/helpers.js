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
  rejected: [],
  withdrawn: [],
};
