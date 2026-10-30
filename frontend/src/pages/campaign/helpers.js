// What the campaign pages share: the nav per role, small helpers and the unit lists.
import { useMemo } from "react";
import { formatNumber as fmt } from "../../lib/format";
import { useTargets } from "../../api/hooks";

// A tone is one of good, warn, bad or neutral; index.css colours each.
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

export const NAV = {
  candidate: [["overview", "Overview"], ["units", "Ward performance"], ["events", "Events"], ["mobilizers", "Mobilizers"], ["team", "Team"], ["payments", "Payments"], ["strategy", "Strategy"]],
  manager: [["overview", "Overview"], ["targets", "Targets"], ["units", "Wards"], ["events", "Events"], ["mobilizers", "Mobilizers"], ["team", "Team"], ["supporters", "Supporters"], ["payments", "Payments"], ["strategy", "Strategy"]],
  mobilizer: [["myevents", "My events"], ["register", "Register supporter"], ["mysupporters", "My supporters"], ["mypayments", "My payments"]],
};
export const ROLE_LABEL = { candidate: "Candidate", manager: "Campaign Manager", mobilizer: "Mobilizer" };

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
