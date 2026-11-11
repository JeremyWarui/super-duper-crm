// Labels and option lists shared across the app: [value, label] lists and the maps built from them.

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

/** Ways to help as text: each area's label, and "Other: …" with what was typed. */
export const helpsWith = (areas, other) => areas.map((a) => (a === "other" ? (other ? `Other: ${other}` : "Other") : AREA_LABEL[a] || a)).join(", ");

/** A volunteer's profession, or what they typed for "other"; "" when none was given. */
export const professionOf = (v) => (v.profession === "other" ? v.profession_other : PROFESSION_LABEL[v.profession]) || "";

// A campaign login's role.
export const ROLE_LABEL = {
  candidate: "Candidate",
  manager: "Campaign Manager",
  coordinator: "Coordinator",
  comms: "Comms officer",
  mobilizer: "Mobilizer",
  agent: "Agent",
};

// A supporter's stated support: [value, label].
export const SUPPORT_LEVELS = [["supporter", "Supporter"], ["undecided", "Undecided"], ["opposed", "Opposed"]];

// An agent's steps toward polling day, in order: [value, label].
export const AGENT_STEPS = [["applied", "Applied"], ["vetted", "Vetted"], ["trained", "Trained"], ["ready", "Ready"]];

// An assignment's status as [label, badge tone].
export const ASSIGNMENT_STATUS = { assigned: ["Assigned", "warn"], done: ["Done", "ok"], cancelled: ["Cancelled", "stone"] };

/** A login's party offices as words: `superAdmin` for a superuser. */
export const officeOf = (user, superAdmin) =>
  user?.is_superuser ? superAdmin : (user?.party_roles || []).map((r) => PARTY_ROLE_LABEL[r] || r).join(", ");
