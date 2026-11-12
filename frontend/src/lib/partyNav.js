// Each party page, the office that opens it and its header; the superuser opens every one.
export const PARTY_PAGES = [
  ["dashboard", "Dashboard", "superuser"],
  ["members", "Members", "membership_officer"],
  ["volunteers", "Volunteers", "membership_officer"],
  ["data-requests", "Data requests", "membership_officer", { kit: true, context: "Personal data", title: "Data requests" }],
  ["aspirants", "Aspirants", "nominations_officer"],
  ["payments-in", "Payments in", "nominations_officer", { kit: true, context: "Money", title: "Payments in" }],
  ["messages", "Messages", "comms_officer", { kit: true, context: "Reach members", title: "Messages" }],
  ["branches", "Branches", "membership_officer", { kit: true, context: "Party structure", title: "Branches" }],
  ["website", "Website", "superuser", { kit: true, context: "Website content", title: "Edit the party website" }],
];

/** The party pages a login's offices open. */
export const pagesFor = (user) => PARTY_PAGES.filter(([, , office]) => user?.is_superuser || (user?.party_roles || []).includes(office));

/**
 * The sidebar for a login: the pages its offices open, and the console for the superuser.
 * An aspirant installation has no party pages.
 */
export function partyNav(user, { aspirant = false } = {}) {
  const pages = aspirant ? [] : pagesFor(user);
  return [
    ...pages.map(([key, label]) => ({ label, to: `/party/${key}` })),
    ...(user?.is_superuser ? [{ label: "Console", to: "/console" }] : []),
  ];
}
