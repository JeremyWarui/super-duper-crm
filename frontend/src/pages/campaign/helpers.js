// What the campaign pages share: the nav per role, small helpers and the unit lists.
import { useMemo } from "react";
import { useCentres, useTargets } from "@/api/hooks";
import { formatDay, nairobiDate } from "@/lib/format";

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


const ALL_FIELD = { label: "Field", items: [["events", "Events"], ["mobilizers", "Mobilizers"], ["agents", "Agents"], ["assignments", "Assignments"], ["supporters", "Contacts"], ["volunteers", "Volunteers"]] };
const REACH_OUT = { label: "Reach out", items: [["announcements", "Announcements"], ["messages", "Messages"], ["calls", "Calls"]] };
const LEAD = [
  { label: "Plan", items: [["overview", "Overview"], ["strategy", "Strategy"], ["targets", "Targets"], ["units", "Wards"]] },
  ALL_FIELD,
  REACH_OUT,
  { label: "People", items: [["team", "Team"], ["signups", "Sign-ups"], ["privacy", "Personal data"]] },
  { label: "Money", items: [["payments", "Payments"], ["contributions", "Contributions"]] },
];
const OWN_WORK = (items) => [{ label: "My work", items }];
// Every role's first group: what the bell holds, as a page.
const INBOX = { label: "Inbox", items: [["notifications", "Notifications"]] };

// Each role's menu: groups of [page key, label], as the permissions map allows (docs/SYSTEM.md, section 2).
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
  comms: [{ label: "Plan", items: [["targets", "Targets"]] }, { label: "Field", items: [["events", "Events"]] }, REACH_OUT],
  mobilizer: OWN_WORK([["myevents", "My events"], ["register", "Add contact"], ["mysupporters", "My contacts"], ["mypayments", "My payments"], ["announcements", "Announcements"]]),
  agent: OWN_WORK([["mycentre", "My centre"], ["myevents", "My events"], ["mypayments", "My payments"], ["announcements", "Announcements"]]),
};

const SITE_WRITERS = ["candidate", "manager", "comms"];

/**
 * A role's menu: those who edit the site get the Website and Settings pages, and an MCA race
 * (`byCentre`) names its units Centres.
 */
export function navFor(role, { byCentre = false } = {}) {
  if (!NAV[role]) return [];
  const groups = [INBOX, ...NAV[role]]
    .map((g) => (byCentre ? { ...g, items: g.items.map(([key, label]) => [key, key === "units" ? "Centres" : label]) } : g));
  if (SITE_WRITERS.includes(role)) groups.push({ label: "Website", items: [["website", "Website"], ["settings", "Settings"]] });
  return groups;
}

/** A role's pages in menu order, as [key, label]. */
export const pagesOf = (role, where) => navFor(role, where).flatMap((group) => group.items);

/** Where a role lands: its first page after the inbox. */
export const landingOf = (role, where) => pagesOf(role, where).find(([key]) => key !== "notifications")?.[0];

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

// The targeted units (wards, or centres in a ward race) a campaign works, in `place` when given.
export function useUnits(campaignId, place) {
  const targets = useTargets(campaignId, place);
  return useMemo(() => (targets.data || []).map((t) => ({
    key: t.id, ward: t.ward, registration_centre: t.registration_centre ?? null, name: t.centre_name || t.ward_name,
  })), [targets.data]);
}

// Ward options for forms: distinct wards from targets, in `place` when given.
export function useWardOptions(campaignId, place) {
  const targets = useTargets(campaignId, place);
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
  const targets = useTargets(ward ? campaignId : undefined);
  const query = useCentres(ward);
  const all = query.data || [];
  const targeted = new Set((targets.data || []).map((t) => t.registration_centre));
  return { centres: all.filter((c) => targeted.has(c.id)), all, targeted, ready: targets.isSuccess, fetched: !query.isFetching && !query.isError };
}

// Who may put a mobilizer on a unit; undefined hides the button.
export const assignerFor = (role, onModal) =>
  isLead(role) ? (unit, holder) => onModal({ type: "assign", unit, holder }) : undefined;


// Attendance counts people reached, so it can't exceed them.
export const attendanceOk = (reached, attended) => reached > 0 && attended <= reached;
export const TOO_MANY_ATTENDED = "Attendance can't be more than those reached.";

/** Whether the role leads the campaign: the candidate or the manager. */
export const isLead = (role) => role === "candidate" || role === "manager";

/** Whether the seat is the whole country (President). */
export const isNational = (campaign) => campaign?.office_level === "national";

/** Whether this role's ward lists load a county at a time: a national seat seen whole. */
export const perCounty = (campaign, role) => isNational(campaign) && isLead(role);

/** The campaign's unit of work: whether it is a polling centre, and its word in lower and title case. */
export function unitOf(campaign) {
  const byCentre = campaign.operational_grain === "centre";
  return { byCentre, noun: byCentre ? "centre" : "ward", Noun: byCentre ? "Centre" : "Ward" };
}
