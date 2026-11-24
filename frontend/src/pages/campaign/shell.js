// What the campaign workspace's frame reads: icons per page, the role's data, the picked area,
// and what needs the role now.
import { createContext, useContext, useEffect, useMemo } from "react";
import {
  Banknote, CalendarDays, ClipboardCheck, ClipboardList, Crosshair, Globe, HandHeart, Heart, Bell, LayoutDashboard, LockKeyhole, Map, MapPin, Megaphone, MessageCircle,
  Phone, Settings, ShieldCheck, Target, UserPlus, UserRoundCog, Users,
} from "lucide-react";
import { useEvents, useMobilizers, useNotices, useReadNotice, useStrategy } from "@/api/hooks";
import { pagesOf, perCounty, reads, useWardOptions } from "./helpers";
import { nairobiDate } from "@/lib/format";

export const ICONS = {
  notifications: Bell,
  announcements: Megaphone,
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

/** A stored notice as the bell and its page show it. */
const noteOf = (n) => ({ key: `notice-${n.id}`, id: n.id, text: n.text, to: n.url, detail: n.detail || "", sender: n.sender || "", at: n.created_at, read: !!n.read_at });

/**
 * What the bell holds: `fresh` unread notices, `earlier` read ones, and `todo`, the work the
 * role has open (wards with no mobilizer, past events not recorded) in the picked `area`.
 * Only `fresh` counts on a badge.
 */
export function workspaceInbox(data, role, area = null) {
  const pages = new Set(pagesOf(role).map(([key]) => key));
  const notes = (data.notices || []).map(noteOf);
  const todo = [];
  const s = data.strategy;
  const units = s ? s.units.filter((u) => !area || u.ward === area) : [];
  const unstaffed = units.filter((u) => !u.has_mobilizer);
  if (unstaffed.length && pages.has("mobilizers")) {
    const n = unstaffed.length;
    const places = unstaffed[0].registration_centre ? "centres" : "wards";
    todo.push({ key: "unstaffed", text: n === 1 ? `${unstaffed[0].unit} has no mobilizer` : `${n} ${places} have no mobilizer`, to: "/campaign/mobilizers" });
  }
  const eventsPage = pages.has("events") ? "events" : pages.has("myevents") && role === "mobilizer" ? "myevents" : null;
  const unrecorded = data.events.filter((e) => e.status === "planned" && e.scheduled_date && e.scheduled_date.slice(0, 10) < nairobiDate() && (!area || e.ward === area));
  if (unrecorded.length && eventsPage && role !== "comms") {
    todo.push({ key: "unrecorded", text: unrecorded.length === 1 ? `Record attendance: ${unrecorded[0].title}` : `${unrecorded.length} past events need their attendance recorded`, to: `/campaign/${eventsPage}` });
  }
  return { fresh: notes.filter((n) => !n.read), earlier: notes.filter((n) => n.read), todo };
}

/** Opening the page a notice points to marks it read. */
export function useReadNoticesOn(path, notices) {
  const read = useReadNotice();
  const due = notices.filter((n) => n.url === path && !n.read_at).map((n) => n.id).join(",");
  useEffect(() => {
    if (due) due.split(",").forEach((id) => read.mutate(id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [due]);
}
