// What the campaign pages share: the nav per role, small helpers and the unit lists.
import { useMemo } from "react";
import { formatNumber as fmt } from "../../lib/format";
import { useTargets } from "../../api/hooks";

// A tone is one of good, warn, bad or neutral; index.css colours each.
export function statusOf(progress) {
  if (progress >= 1) return { label: "Target met", tone: "good" };
  if (progress >= 0.6) return { label: "Building", tone: "warn" };
  return { label: "Behind", tone: "bad" };
}

// The mobilizer on a unit: its ward, or its registration centre in a ward race.
export const holderOf = (mobilizers, unit) =>
  mobilizers.find((m) => m.ward === unit.ward && (m.registration_centre ?? null) === (unit.registration_centre ?? null));

export const kes = (n) => `KES ${fmt(n)}`;

const ALL_FIELD = { label: "Field", items: [["events", "Events"], ["mobilizers", "Mobilizers"], ["supporters", "Supporters"], ["volunteers", "Volunteers"]] };
const LEAD = [
  { label: "Plan", items: [["overview", "Overview"], ["strategy", "Strategy"], ["targets", "Targets"], ["units", "Wards"]] },
  ALL_FIELD,
  { label: "People", items: [["team", "Team"]] },
  { label: "Money", items: [["payments", "Payments"]] },
];
const OWN_WORK = (items) => [{ label: "My work", items }];

// Each role's menu: groups of [page key, label], as the permissions map allows (docs/Product_Design.md, 0.2).
export const NAV = {
  candidate: LEAD,
  manager: LEAD,
  coordinator: [
    { label: "Plan", items: [["overview", "Overview"], ["strategy", "Strategy"], ["units", "Wards"]] },
    ALL_FIELD,
    { label: "Money", items: [["payments", "Payments"]] },
  ],
  comms: [{ label: "Field", items: [["events", "Events"]] }],
  mobilizer: OWN_WORK([["myevents", "My events"], ["register", "Register supporter"], ["mysupporters", "My supporters"], ["mypayments", "My payments"]]),
  agent: OWN_WORK([["myevents", "My events"], ["mypayments", "My payments"]]),
};

/** A role's pages in menu order, as [key, label]. */
export const pagesOf = (role) => (NAV[role] || []).flatMap((group) => group.items);

export const ROLE_LABEL = {
  candidate: "Candidate",
  manager: "Campaign Manager",
  coordinator: "Coordinator",
  comms: "Comms officer",
  mobilizer: "Mobilizer",
  agent: "Agent",
};

// What a role's access covers, under its label in the sidebar; a coordinator's names their area.
export const ROLE_NOTE = {
  candidate: "Full access to your campaign.",
  manager: "Full access to this campaign.",
  coordinator: "Limited to your area.",
  comms: "Events and the website.",
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

// Who may put a mobilizer on a unit; undefined hides the button.
export const assignerFor = (role, onModal) =>
  role === "manager" || role === "candidate" ? (unit, holder) => onModal({ type: "assign", unit, holder }) : undefined;
