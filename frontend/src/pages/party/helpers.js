
/** A place filter with nothing chosen. */
export const NO_PLACE = { county: "", constituency: "", ward: "" };

/** Rows each party list fetches at a time. */
export const PAGE_SIZE = 50;

export const PARTY_ROLES = [
  ["membership_officer", "Membership Officer"],
  ["nominations_officer", "Nominations Officer"],
  ["comms_officer", "Comms Officer"],
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
  approved: "ok",
  suspended: "warn",
  rejected: "bad",
  withdrawn: "stone",
};

// The moves an officer offers for each status: [new status, button label].
export const MOVES = {
  pending: [["approved", "Approve"], ["rejected", "Reject"], ["withdrawn", "Withdraw"]],
  approved: [["suspended", "Suspend"], ["withdrawn", "Withdraw"]],
  suspended: [["approved", "Reinstate"], ["withdrawn", "Withdraw"]],
  rejected: [["withdrawn", "Withdraw"]],
  withdrawn: [],
};

export const AREAS = [
  ["fundraising", "Fundraising Support"],
  ["door_to_door", "Door-to-door Campaign"],
  ["mobilising_voters", "Mobilising Voters"],
  ["social_media", "Social Media Support"],
  ["recruiting", "Recruiting Volunteers"],
  ["materials", "Distributing Campaign Materials"],
  ["data_collection", "Data Collection"],
  ["community_listening", "Community Listening"],
  ["barazas", "Holding Barazas & Household Meetings"],
  ["other", "Other"],
];

export const AREA_LABEL = Object.fromEntries(AREAS);

export const PROFESSIONS = [
  ["farmer", "Farmer"],
  ["teacher", "Teacher"],
  ["business", "Business"],
  ["student", "Student"],
  ["other", "Other"],
];

export const PROFESSION_LABEL = Object.fromEntries(PROFESSIONS);

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
  active: "ok",
  inactive: "stone",
  withdrawn: "stone",
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
  draft: "stone",
  submitted: "warn",
  approved: "ok",
  suspended: "warn",
  rejected: "bad",
  withdrawn: "stone",
};

// A member's own view of their membership and nomination: [label, badge tone] per status.
export const MY_MEMBER_STATUS = { approved: ["Active member", "ok"], pending: ["Application pending", "warn"], suspended: ["Suspended", "bad"] };
export const MY_ASPIRANT_STATUS = { draft: ["Not submitted", "warn"], submitted: ["With the vetting team", "info"], approved: ["Approved aspirant", "ok"], suspended: ["Suspended", "bad"] };

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
