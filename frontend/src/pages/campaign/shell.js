// What the campaign workspace's frame reads: icons per page, the role's data, the picked area,
// and what needs the role now.
import { createContext, useContext, useMemo } from "react";
import {
  Banknote, CalendarDays, Flag, ClipboardCheck, ClipboardList, Contact, Crosshair, Globe, HandHeart, Heart, LayoutDashboard, LockKeyhole, Map, MapPin, MessageCircle, QrCode,
  Settings, ShieldCheck, Target, UserPlus, UserRoundCog, Users,
} from "lucide-react";
import { useEvents, useMobilizers, useStrategy, useSupporters } from "@/api/hooks";
import { pagesOf, reads, useWardOptions } from "./helpers";
import { nairobiDate } from "@/lib/format";

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
  contributions: Banknote,
  myevents: CalendarDays,
  register: UserPlus,
  mysupporters: Heart,
  mypayments: Banknote,
  website: Globe,
  settings: Settings,
  recruitment: QrCode,
  members: Contact,
  signups: ClipboardCheck,
  agents: ShieldCheck,
  mycentre: MapPin,
  assignments: ClipboardList,
  messages: MessageCircle,
  party: Flag,
  privacy: LockKeyhole,
};

/** The data the shell reads for this role; a query the role may not make is never sent. */
export function useShellData(campaign, role) {
  const id = (what) => (reads(role, what) ? campaign.id : undefined);
  const wardOptions = useWardOptions(id("targets"));
  const strategy = useStrategy(id("strategy"));
  const events = useEvents(id("events"));
  const supporters = useSupporters(id("supporters"));
  const mobilizers = useMobilizers(id("mobilizers"));
  const wards = useMemo(() => [...wardOptions].sort((a, b) => a.name.localeCompare(b.name)), [wardOptions]);
  return { wards, strategy: strategy.data, events: events.data || [], supporters: supporters.data || [], mobilizers: mobilizers.data || [] };
}

/** The area a person has picked in the top bar, for pages to narrow to; null is every area. */
export const AreaContext = createContext({ area: null, setArea: () => {}, wards: [] });
export const useWorkspaceArea = () => useContext(AreaContext);

/** What needs the role now: wards with no mobilizer, and past events not yet recorded. */
export function workspaceAlerts(data, role) {
  const pages = new Set(pagesOf(role).map(([key]) => key));
  const out = [];
  const empty = (data.strategy?.units || []).filter((u) => !u.has_mobilizer);
  if (empty.length && pages.has("mobilizers")) {
    out.push({ key: "unstaffed", text: empty.length === 1 ? `${empty[0].unit} has no mobilizer` : `${empty.length} wards have no mobilizer`, to: "/campaign/mobilizers" });
  }
  const eventsPage = pages.has("events") ? "events" : pages.has("myevents") && role === "mobilizer" ? "myevents" : null;
  const unrecorded = data.events.filter((e) => e.status === "planned" && e.scheduled_date && e.scheduled_date.slice(0, 10) < nairobiDate());
  if (unrecorded.length && eventsPage && role !== "comms") {
    out.push({ key: "unrecorded", text: unrecorded.length === 1 ? `Record attendance: ${unrecorded[0].title}` : `${unrecorded.length} past events need their attendance recorded`, to: `/campaign/${eventsPage}` });
  }
  return out;
}

