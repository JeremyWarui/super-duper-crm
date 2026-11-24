// What the campaign workspace's frame reads: icons per page, the role's data, the picked area,
// and what needs the role now.
import { createContext, useContext, useEffect, useMemo } from "react";
import {
  Banknote, CalendarDays, ClipboardCheck, ClipboardList, Crosshair, Globe, HandHeart, Heart, LayoutDashboard, LockKeyhole, Map, MapPin, MessageCircle,
  Phone, Settings, ShieldCheck, Target, UserPlus, UserRoundCog, Users,
} from "lucide-react";
import { useEvents, useMobilizers, useNotices, useReadNotice, useStrategy } from "@/api/hooks";
import { pagesOf, perCounty, reads, useWardOptions } from "./helpers";
import { nairobiDate } from "@/lib/format";

export const ICONS = {
  calls: Phone,
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
  signups: ClipboardCheck,
  agents: ShieldCheck,
  mycentre: MapPin,
  assignments: ClipboardList,
  messages: MessageCircle,
  privacy: LockKeyhole,
};

/** The data the shell reads for this role; a query the role may not make is never sent.
 *  Contacts are searched on the server, so `contactsFor` is only the campaign to search. */
export function useShellData(campaign, role) {
  const id = (what) => (reads(role, what) ? campaign.id : undefined);
  // A national seat seen whole has too many wards to list; its pages pick a county instead.
  const wardOptions = useWardOptions(perCounty(campaign, role) ? undefined : id("targets"));
  const strategy = useStrategy(id("strategy"));
  const events = useEvents(id("events"));
  const mobilizers = useMobilizers(id("mobilizers"));
  const notices = useNotices();
  const wards = useMemo(() => [...wardOptions].sort((a, b) => a.name.localeCompare(b.name)), [wardOptions]);
  return { wards, strategy: strategy.data, events: events.data || [], contactsFor: id("supporters"), mobilizers: mobilizers.data || [], notices: notices.data || [] };
}

/** The area a person has picked in the top bar, for pages to narrow to; null is every area. */
export const AreaContext = createContext({ area: null, setArea: () => {}, wards: [] });
export const useWorkspaceArea = () => useContext(AreaContext);

/** What needs the role now: wards with no mobilizer, and past events not yet recorded. */
export function workspaceAlerts(data, role) {
  const pages = new Set(pagesOf(role).map(([key]) => key));
  const out = (data.notices || []).map((n) => ({ key: `notice-${n.id}`, text: n.text, to: n.url }));
  const s = data.strategy;
  const empty = s ? s.unit_count - s.staffed_count : 0;
  if (empty && pages.has("mobilizers")) {
    const only = empty === 1 && s.units.find((u) => !u.has_mobilizer);
    out.push({ key: "unstaffed", text: only ? `${only.unit} has no mobilizer` : `${empty} ${empty === 1 ? "ward has" : "wards have"} no mobilizer`, to: "/campaign/mobilizers" });
  }
  const eventsPage = pages.has("events") ? "events" : pages.has("myevents") && role === "mobilizer" ? "myevents" : null;
  const unrecorded = data.events.filter((e) => e.status === "planned" && e.scheduled_date && e.scheduled_date.slice(0, 10) < nairobiDate());
  if (unrecorded.length && eventsPage && role !== "comms") {
    out.push({ key: "unrecorded", text: unrecorded.length === 1 ? `Record attendance: ${unrecorded[0].title}` : `${unrecorded.length} past events need their attendance recorded`, to: `/campaign/${eventsPage}` });
  }
  return out;
}

/** Opening the page a notice points to marks it read. */
export function useReadNoticesOn(path, notices) {
  const read = useReadNotice();
  const due = notices.filter((n) => n.url === path).map((n) => n.id).join(",");
  useEffect(() => {
    if (due) due.split(",").forEach((id) => read.mutate(id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [due]);
}
