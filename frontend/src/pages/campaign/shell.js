// What the campaign workspace's frame reads: icons per page, the role's data, the picked area,
// and what needs the role now.
import { createContext, useContext, useMemo } from "react";
import {
  Banknote, CalendarDays, Flag, ClipboardCheck, ClipboardList, Crosshair, Globe, HandHeart, Heart, LayoutDashboard, Map, MapPin, MessageCircle, QrCode,
  Settings, ShieldCheck, Target, UserPlus, UserRoundCog, Users,
} from "lucide-react";
import { useEvents, useMobilizers, useStrategy, useSupporters, useTargets } from "../../api/hooks";
import { pagesOf, reads } from "./helpers";

export const ICONS = {
  overview: LayoutDashboard,
  strategy: Target,
  targets: Crosshair,
  units: Map,
  events: CalendarDays,
  mobilizers: Users,
  supporters: Heart,
  volunteers: HandHeart,
  team: UserRoundCog,
  payments: Banknote,
  myevents: CalendarDays,
  register: UserPlus,
  mysupporters: Heart,
  mypayments: Banknote,
  website: Globe,
  settings: Settings,
  recruitment: QrCode,
  signups: ClipboardCheck,
  agents: ShieldCheck,
  mycentre: MapPin,
  assignments: ClipboardList,
  messages: MessageCircle,
  party: Flag,
};

/** The data the shell reads for this role; a query the role may not make is never sent. */
export function useShellData(campaign, role) {
  const id = (what) => (reads(role, what) ? campaign.id : undefined);
  const targets = useTargets(id("targets"));
  const strategy = useStrategy(id("strategy"));
  const events = useEvents(id("events"));
  const supporters = useSupporters(id("supporters"));
  const mobilizers = useMobilizers(id("mobilizers"));
  const wards = useMemo(() => {
    const seen = new Set();
    const out = [];
    for (const t of targets.data || []) {
      if (t.ward && !seen.has(t.ward)) { seen.add(t.ward); out.push({ id: t.ward, name: t.ward_name }); }
    }
    return out.sort((a, b) => a.name.localeCompare(b.name));
  }, [targets.data]);
  return { wards, strategy: strategy.data, events: events.data || [], supporters: supporters.data || [], mobilizers: mobilizers.data || [] };
}

/** The area a person has picked in the top bar, for pages to narrow to; null is every area. */
export const AreaContext = createContext({ area: null, setArea: () => {}, wards: [] });
export const useWorkspaceArea = () => useContext(AreaContext);

const today = () => new Date().toISOString().slice(0, 10);

/** What needs the role now: wards with no mobilizer, and past events not yet recorded. */
export function workspaceAlerts(data, role) {
  const pages = new Set(pagesOf(role).map(([key]) => key));
  const out = [];
  const empty = (data.strategy?.units || []).filter((u) => !u.has_mobilizer);
  if (empty.length && pages.has("mobilizers")) {
    out.push({ key: "unstaffed", text: empty.length === 1 ? `${empty[0].unit} has no mobilizer` : `${empty.length} wards have no mobilizer`, to: "/campaign/mobilizers" });
  }
  const eventsPage = pages.has("events") ? "events" : pages.has("myevents") && role === "mobilizer" ? "myevents" : null;
  const unrecorded = data.events.filter((e) => e.status === "planned" && e.scheduled_date && e.scheduled_date.slice(0, 10) < today());
  if (unrecorded.length && eventsPage && role !== "comms") {
    out.push({ key: "unrecorded", text: unrecorded.length === 1 ? `Record attendance: ${unrecorded[0].title}` : `${unrecorded.length} past events need their attendance recorded`, to: `/campaign/${eventsPage}` });
  }
  return out;
}

