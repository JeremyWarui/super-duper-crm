/** Rows each party list fetches at a time. */
export const PAGE_SIZE = 50;

// The moves an officer offers for each status: [new status, button label].
export const MOVES = {
  pending: [["approved", "Approve"], ["rejected", "Reject"], ["withdrawn", "Withdraw"]],
  approved: [["suspended", "Suspend"], ["withdrawn", "Withdraw"]],
  suspended: [["approved", "Reinstate"], ["withdrawn", "Withdraw"]],
  rejected: [["withdrawn", "Withdraw"]],
  withdrawn: [],
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
