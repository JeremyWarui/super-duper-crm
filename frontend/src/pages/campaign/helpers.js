// What the campaign pages share: the nav per role, small helpers and the unit lists.
import { useMemo } from "react";
import { useCentres, useTargets } from "../../api/hooks";
import { isEmail } from "../../lib/email";
import { formatDay, nairobiDate } from "../../lib/format";

/**
 * An event's day as people in Nairobi read it: "Today" or "Sat 7 Nov", with the time when it has one.
 * A date picked without a time is stored as midnight UTC and shows no time.
 */
export function eventDay(e, now = new Date()) {
  if (!e.scheduled_date) return "No date yet";
  const at = new Date(e.scheduled_date);
  const day = nairobiDate(at) === nairobiDate(now) ? "Today" : formatDay(e.scheduled_date, { weekday: "short", day: "numeric", month: "short" });
  const timed = at.getUTCHours() || at.getUTCMinutes();
  return timed ? `${day} · ${at.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Africa/Nairobi" })}` : day;
}

// How far a unit is towards its target, as a label and a tone of good, warn or bad.
export function statusOf(progress) {
  if (progress >= 1) return { label: "Target met", tone: "good" };
  if (progress >= 0.6) return { label: "Building", tone: "warn" };
  return { label: "Behind", tone: "bad" };
}

// The mobilizer on a unit: its ward, or its registration centre in a ward race.
export const holderOf = (mobilizers, unit) =>
  mobilizers.find((m) => m.ward === unit.ward && (m.registration_centre ?? null) === (unit.registration_centre ?? null));


const ALL_FIELD = { label: "Field", items: [["events", "Events"], ["mobilizers", "Mobilizers"], ["agents", "Agents"], ["assignments", "Assignments"], ["supporters", "Supporters"], ["volunteers", "Volunteers"]] };
const REACH_OUT = { label: "Reach out", items: [["messages", "Messages"]] };
const LEAD = [
  { label: "Plan", items: [["overview", "Overview"], ["strategy", "Strategy"], ["targets", "Targets"], ["units", "Wards"]] },
  ALL_FIELD,
  REACH_OUT,
  { label: "People", items: [["team", "Team"], ["signups", "Sign-ups"], ["privacy", "Personal data"]] },
  { label: "Money", items: [["payments", "Payments"], ["contributions", "Contributions"]] },
];
const OWN_WORK = (items) => [{ label: "My work", items }];

// Each role's menu: groups of [page key, label], as the permissions map allows (docs/Product_Design.md, 0.2).
export const NAV = {
  candidate: LEAD,
  manager: LEAD,
  coordinator: [
    { label: "Plan", items: [["overview", "Overview"], ["strategy", "Strategy"], ["units", "Wards"]] },
    ALL_FIELD,
    REACH_OUT,
    { label: "People", items: [["signups", "Sign-ups"]] },
    { label: "Money", items: [["payments", "Payments"]] },
  ],
  comms: [{ label: "Field", items: [["events", "Events"]] }, REACH_OUT],
  mobilizer: OWN_WORK([["myevents", "My events"], ["register", "Register supporter"], ["mysupporters", "My supporters"], ["mypayments", "My payments"]]),
  agent: OWN_WORK([["mycentre", "My centre"], ["myevents", "My events"], ["mypayments", "My payments"]]),
};

const SITE_WRITERS = ["candidate", "manager", "comms"];
// A party nominee's workspace has the party feed and its sharing switches.
const FEED_READERS = ["candidate", "manager", "comms"];

/**
 * A role's menu where it works: an aspirant installation adds the Website and Settings pages for
 * those who edit the site; the party workspace adds Recruitment and Party members for its
 * coordinators; a hosted workspace adds the party feed. An MCA race (`byCentre`) names its units
 * Centres.
 */
export function navFor(role, { aspirant = false, partyWorkspace = false, hosted = false, byCentre = false } = {}) {
  const feed = hosted && !aspirant && FEED_READERS.includes(role);
  const groups = (NAV[role] || [])
    .map((g) => (feed && g === REACH_OUT ? { ...g, items: [...g.items, ["party", "Party feed"]] } : g))
    .map((g) => (byCentre ? { ...g, items: g.items.map(([key, label]) => [key, key === "units" ? "Centres" : label]) } : g));
  const extra = [];
  if (aspirant && SITE_WRITERS.includes(role)) extra.push({ label: "Website", items: [["website", "Website"], ["settings", "Settings"]] });
  if (partyWorkspace && role === "coordinator") extra.push({ label: "Recruit", items: [["recruitment", "Recruitment"], ["members", "Party members"]] });
  return [...groups, ...extra];
}

/** A role's pages in menu order, as [key, label]. */
export const pagesOf = (role, where) => navFor(role, where).flatMap((group) => group.items);

// What a role's access covers, under its label in the sidebar; a coordinator's names their area.
export const ROLE_NOTE = {
  candidate: "Full access to your campaign.",
  manager: "Full access to this campaign.",
  coordinator: "Limited to your area.",
  comms: "Events, messages and the website.",
  mobilizer: "Your own ward.",
  agent: "Your centre and assignments.",
};

// Which campaign data each role may read, for the shell's search, area picker and alerts.
export const READS = {
  strategy: ["candidate", "manager", "coordinator"],
  targets: ["candidate", "manager", "coordinator", "mobilizer"],
  events: ["candidate", "manager", "coordinator", "comms", "mobilizer", "agent"],
  supporters: ["candidate", "manager", "coordinator", "mobilizer"],
  mobilizers: ["candidate", "manager", "coordinator", "mobilizer"],
};
export const reads = (role, what) => READS[what].includes(role);

// The targeted units (wards, or centres in a ward race) a campaign works.
export function useUnits(campaignId) {
  const targets = useTargets(campaignId);
  return useMemo(() => (targets.data || []).map((t) => ({
    key: t.id, ward: t.ward, registration_centre: t.registration_centre ?? null, name: t.centre_name || t.ward_name,
  })), [targets.data]);
}

// Ward options for forms: distinct wards from targets.
export function useWardOptions(campaignId) {
  const targets = useTargets(campaignId);
  return useMemo(() => {
    const seen = {}; const out = [];
    (targets.data || []).forEach((t) => { if (t.ward && !seen[t.ward]) { seen[t.ward] = 1; out.push({ id: t.ward, name: t.ward_name }); } });
    return out;
  }, [targets.data]);
}

/**
 * The centres of `ward` that carry a target (`centres`), every centre of the ward (`all`), the targeted
 * centre ids, whether the targets are in (`ready`) and whether the centres have come back (`fetched`).
 */
export function useTargetedCentres(campaignId, ward) {
  const targets = useTargets(campaignId);
  const query = useCentres(ward);
  const all = query.data || [];
  const targeted = new Set((targets.data || []).map((t) => t.registration_centre));
  return { centres: all.filter((c) => targeted.has(c.id)), all, targeted, ready: targets.isSuccess, fetched: !query.isFetching && !query.isError };
}

// Who may put a mobilizer on a unit; undefined hides the button.
export const assignerFor = (role, onModal) =>
  isLead(role) ? (unit, holder) => onModal({ type: "assign", unit, holder }) : undefined;

/** Whether a new login's username (3 or more characters) and email are usable. */
export const loginReady = ({ username, email }) => username.trim().length >= 3 && isEmail(email);

/** A new login's name, username, email and phone as the team routes take them. */
export function loginBody({ name, username, email, phone }) {
  const [first, ...rest] = name.trim().split(/\s+/);
  return { username: username.trim().toLowerCase(), first_name: first, last_name: rest.join(" "), phone: phone.trim(), email: email.trim() };
}

// Attendance counts people reached, so it can't exceed them.
export const attendanceOk = (reached, attended) => reached > 0 && attended <= reached;
export const TOO_MANY_ATTENDED = "Attendance can't be more than those reached.";

/** Whether the role leads the campaign: the candidate or the manager. */
export const isLead = (role) => role === "candidate" || role === "manager";

/** The campaign's unit of work: whether it is a polling centre, and its word in lower and title case. */
export function unitOf(campaign) {
  const byCentre = campaign.operational_grain === "centre";
  return { byCentre, noun: byCentre ? "centre" : "ward", Noun: byCentre ? "Centre" : "Ward" };
}
