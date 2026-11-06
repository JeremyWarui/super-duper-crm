// The campaign workspace's frame pieces: brand, seat card, access footer, and the top bar's
// search, area picker, notifications and help. Each reads only data the role may read.
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Bell, CircleHelp, Search } from "lucide-react";
import { useSite } from "../../api/hooks";
import { formatNumber } from "../../lib/format";
import { ROLE_LABEL, ROLE_NOTE, pagesOf } from "./helpers";
import { useWorkspaceArea, workspaceAlerts } from "./shell";

type Ward = { id: string; name: string };
type Row = { id: string; [field: string]: any };
type Hit = { key: string; to: string; kind: string; label: string; detail: string };
type ShellData = { wards: Ward[]; strategy?: any; events: Row[]; supporters: Row[]; mobilizers: Row[] };
type Campaign = { title: string; candidate_name: string; seat: string; area_name: string; election_date: string | null };

const initials = (name) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();

export function WorkspaceBrand({ name }: { name?: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <span aria-hidden className="flex size-[34px] shrink-0 items-center justify-center rounded-[9px] bg-accent font-display text-[17px] font-extrabold text-ink">
        {(name || "C").trim()[0].toUpperCase()}
      </span>
      <div className="flex min-w-0 flex-col">
        <span className="truncate font-display text-[18px] font-extrabold">{name || "Campaign"}</span>
        <span className="text-meta text-muted-foreground">Campaign workspace</span>
      </div>
    </div>
  );
}

const daysTo = (iso: string) => Math.ceil((new Date(`${iso}T00:00:00`).getTime() - new Date(new Date().toDateString()).getTime()) / 86400000);

/** Who the campaign is for and what it contests; the party workspace reads "National". */
export function SeatCard({ campaign, winNumber }: { campaign: Campaign; winNumber?: number }) {
  const name = campaign.candidate_name || campaign.title;
  const where = [campaign.seat.replace(/ seat$/, ""), campaign.area_name].filter(Boolean).join(" · ");
  const days = campaign.election_date ? daysTo(campaign.election_date) : null;
  return (
    <section aria-label="Campaign" className="flex flex-col gap-2.5 rounded-[14px] border border-line bg-ground-app p-3.5">
      <div className="flex items-center gap-2.5">
        <span aria-hidden className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary text-ui font-extrabold text-accent">
          {initials(name)}
        </span>
        <div className="flex min-w-0 flex-col">
          <span className="truncate text-[15px] font-bold">{name}</span>
          <span className="text-small text-muted-foreground">{where}</span>
        </div>
      </div>
      {winNumber || (days !== null && days >= 0) ? (
        <div className="flex flex-wrap gap-1.5">
          {winNumber ? <span className="rounded-full bg-[#FFF3CC] px-2.5 py-[3px] text-meta font-bold text-[#6B5100]">Win no. {formatNumber(winNumber)}</span> : null}
          {days !== null && days >= 0 ? (
            <span className="rounded-full bg-primary-tint px-2.5 py-[3px] text-meta font-bold text-primary">
              {days === 0 ? "Election day" : `${days} ${days === 1 ? "day" : "days"} to election day`}
            </span>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

/** "Your access": the role, and what it covers; a coordinator's names their wards. */
export function AccessFooter({ role, wards }: { role: string; wards: Ward[] }) {
  const note = role === "coordinator" && wards.length
    ? `Limited to ${wards.map((w) => w.name).join(", ")}.`
    : ROLE_NOTE[role];
  return (
    <>
      <span className="text-meta text-muted-foreground">Your access</span>
      <span className="self-start rounded-full bg-primary-tint px-2.5 py-1 text-ui font-bold text-primary">{ROLE_LABEL[role]}</span>
      <span className="text-meta text-muted-foreground">{note}</span>
    </>
  );
}

function usePanel() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDown); document.removeEventListener("keydown", onKey); };
  }, [open]);
  return { open, setOpen, ref };
}

const PANEL = "absolute right-0 z-50 mt-2 flex w-[min(92vw,380px)] flex-col gap-1 rounded-photo border border-line bg-white p-2 shadow-pop";
const ICON_BUTTON = "relative flex size-11 cursor-pointer items-center justify-center rounded-full hover:bg-stone";
const ROW = "flex min-h-11 flex-col justify-center rounded-lg px-3 py-1.5 text-ink no-underline hover:bg-stone";

/** Search the wards, events, supporters and mobilizers the role reads; Ctrl K or Cmd K focuses it. */
export function WorkspaceSearch({ data, role }: { data: ShellData; role: string }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); input.current?.focus(); }
      if (e.key === "Escape") setOpen(false);
    };
    const onDown = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => { document.removeEventListener("keydown", onKey); document.removeEventListener("mousedown", onDown); };
  }, []);
  const needle = q.trim().toLowerCase();
  const hits = useMemo(() => {
    if (needle.length < 2) return [];
    const has = new Set(pagesOf(role).map(([key]) => key));
    const page = (...keys: string[]) => keys.find((k) => has.has(k));
    const match = (...texts: (string | undefined)[]) => texts.some((t) => (t || "").toLowerCase().includes(needle));
    const out: Hit[] = [];
    const add = (rows: Row[], to: string | undefined, kind: string, label: (r: Row) => string, detail: (r: Row) => string) => {
      if (!to) return;
      for (const r of rows) if (match(label(r), detail(r))) out.push({ key: `${kind}-${r.id}`, to: `/campaign/${to}`, kind, label: label(r), detail: detail(r) });
    };
    add(data.wards as Row[], page("units", "targets"), "Ward", (w) => w.name, () => "");
    add(data.events, page("events", "myevents"), "Event", (e) => e.title, (e) => e.venue);
    add(data.supporters, page("supporters", "mysupporters"), "Supporter", (s) => s.full_name, (s) => s.phone);
    add(data.mobilizers, page("mobilizers"), "Mobilizer", (m) => m.full_name, (m) => m.phone);
    return out.slice(0, 8);
  }, [needle, data, role]);
  return (
    <div ref={ref} className="relative">
      <label className="flex h-[42px] max-sm:h-11 items-center gap-2.5 rounded-full bg-[#F4F3EF] px-4">
        <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden />
        <input
          ref={input}
          type="search"
          aria-label="Search the workspace"
          placeholder="Search supporters, wards, events…"
          value={q}
          onChange={(e) => { setQ(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          className="min-w-0 flex-1 border-0 bg-transparent text-body outline-offset-4"
        />
        <kbd className="hidden rounded-sm border border-[#E8E8E4] bg-white px-1.5 py-0.5 text-meta font-bold text-muted-foreground lg:inline">Ctrl K</kbd>
      </label>
      {open && needle.length >= 2 ? (
        <div className={`${PANEL} left-0 right-auto w-full`}>
          {hits.length === 0 ? <span className="px-3 py-2 text-ui text-muted-foreground">Nothing you can see matches.</span> : null}
          {hits.length ? (
            <ul aria-label="Search results" className="m-0 flex list-none flex-col p-0">
              {hits.map((h) => (
                <li key={h.key}>
                  <Link to={h.to} onClick={() => setOpen(false)} className={ROW}>
                    <span className="text-ui font-bold">{h.label}</span>
                    <span className="text-meta text-muted-foreground">{[h.kind, h.detail].filter(Boolean).join(" · ")}</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/** The wards the role may read; nothing when it reads none. */
export function AreaPicker() {
  const { area, setArea, wards } = useWorkspaceArea();
  if (!wards.length) return null;
  return (
    <label className="flex items-center gap-1.5 text-meta font-semibold text-muted-foreground">
      Area
      <select
        value={area ?? ""}
        onChange={(e) => setArea(e.target.value || null)}
        className="h-10 max-sm:h-11 max-w-[180px] rounded-full border border-line-control bg-white px-2.5 text-ui font-bold text-ink"
      >
        <option value="">{wards.length === 1 ? wards[0].name : "All wards"}</option>
        {wards.length > 1 ? wards.map((w) => <option key={w.id} value={w.id}>{w.name}</option>) : null}
      </select>
    </label>
  );
}

export function WorkspaceAlerts({ data, role }: { data: ShellData; role: string }) {
  const { open, setOpen, ref } = usePanel();
  const notes = workspaceAlerts(data, role);
  return (
    <div ref={ref} className="relative">
      <button type="button" aria-expanded={open} aria-controls="workspace-notifications" onClick={() => setOpen(!open)} className={ICON_BUTTON}
        aria-label={notes.length ? `Notifications, ${notes.length} new` : "Notifications, nothing new"}>
        <Bell className="size-5" aria-hidden />
        {notes.length ? <span aria-hidden className="absolute top-1.5 right-1.5 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-destructive px-1 text-[11px] font-extrabold text-white">{notes.length}</span> : null}
      </button>
      {open ? (
        <div id="workspace-notifications" role="region" aria-label="Notifications" className={PANEL}>
          {notes.length === 0 ? <span className="px-3 py-2 text-ui text-muted-foreground">Nothing needs you right now.</span> : null}
          {notes.map((n) => (
            <Link key={n.key} to={n.to} onClick={() => setOpen(false)} className={ROW}>
              <span className="text-ui font-bold">{n.text}</span>
            </Link>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/** Who to ask: the site's contacts. */
export function WorkspaceHelp() {
  const { open, setOpen, ref } = usePanel();
  const site = (useSite().data || {}) as { contact_phone?: string; contact_email?: string };
  return (
    <div ref={ref} className="relative">
      <button type="button" aria-expanded={open} aria-controls="workspace-help" aria-label="Help" onClick={() => setOpen(!open)} className={ICON_BUTTON}>
        <CircleHelp className="size-5" aria-hidden />
      </button>
      {open ? (
        <div id="workspace-help" className={PANEL}>
          <span className="px-3 pt-2 text-ui font-bold">Need help?</span>
          <span className="px-3 pb-1 text-meta text-muted-foreground">Your campaign manager runs this workspace. For a password or a login, ask the office.</span>
          {site.contact_phone ? <a href={`tel:${site.contact_phone}`} className={ROW}><span className="text-ui font-semibold">Call {site.contact_phone}</span></a> : null}
          {site.contact_email ? <a href={`mailto:${site.contact_email}`} className={ROW}><span className="text-ui font-semibold">Email {site.contact_email}</span></a> : null}
        </div>
      ) : null}
    </div>
  );
}
