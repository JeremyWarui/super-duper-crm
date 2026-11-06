import { useState } from "react";
import { useEvents } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FilterPills } from "@/components/ui/tabs";
import { formatNumber as fmt } from "@/lib/format";
import WsHeader, { KitError, KitLoading } from "./WsHeader";

const ASSIGNERS = ["candidate", "manager", "coordinator"];
const WHEN = { Upcoming: (e) => e.status !== "done", Past: (e) => e.status === "done" };
const dayOf = (e) => (e.scheduled_date ? new Date(e.scheduled_date) : null);

function Figure({ label, value }) {
  return (
    <div className="flex flex-col items-end">
      <span className="text-meta text-muted-foreground">{label}</span>
      <span className="text-[18px] font-extrabold tabular-nums">{value}</span>
    </div>
  );
}

function EventCard({ event: e, onRecord, onInvite, onQr, onAssign }) {
  const done = e.status === "done";
  const day = dayOf(e);
  const rate = e.number_attended > 0 ? ` (${Math.round((e.signups / e.number_attended) * 100)}%)` : "";
  return (
    <article className="flex flex-wrap items-center gap-[18px] rounded-xl border border-line bg-card p-5">
      <div className="flex h-[72px] w-16 flex-none flex-col items-center justify-center rounded-lg bg-primary-tint text-primary">
        {day ? (
          <>
            <span className="text-[11px] font-extrabold tracking-[0.08em] uppercase">{day.toLocaleDateString("en-GB", { month: "short" })}</span>
            <span className="font-display text-[24px] leading-none font-extrabold">{day.getDate()}</span>
          </>
        ) : <span className="text-meta font-bold">No date</span>}
      </div>
      <div className="flex min-w-0 flex-[1_1_240px] flex-col gap-1">
        <span className="text-meta font-extrabold tracking-[0.08em] text-primary uppercase">{e.ward_name}</span>
        <h2 className="text-[18px] font-bold">{e.title}</h2>
        <span className="text-ui text-muted-foreground">{e.venue || "No venue yet"}</span>
      </div>
      <div className="flex flex-wrap items-center gap-5">
        {done ? (
          <>
            <Figure label="Reached" value={fmt(e.number_reached)} />
            <Figure label="Attended" value={fmt(e.number_attended)} />
            <Figure label="Turnout" value={`${e.turnout_pct}%`} />
          </>
        ) : null}
        <Figure label="Signed up" value={`${fmt(e.signups)}${rate}`} />
        <Badge tone={done ? "ok" : "warn"}>{done ? "Done" : "Planned"}</Badge>
      </div>
      {(onRecord || onInvite || onQr || onAssign) && (
        <div className="flex w-full flex-wrap gap-2 border-t border-line-soft pt-3">
          {!done && onRecord && <Button shape="rounded" size="sm" onClick={() => onRecord(e)}>Record</Button>}
          {onInvite && <Button shape="rounded" size="sm" variant="quiet" onClick={() => onInvite(e)}>Invite</Button>}
          {onQr && e.signup_code && <Button shape="rounded" size="sm" variant="quiet" onClick={() => onQr(e)}>{e.signups_open ? "Sign-up QR" : "Closed"}</Button>}
          {onAssign && e.status !== "cancelled" && <Button shape="rounded" size="sm" variant="quiet" onClick={() => onAssign(e)} aria-label={`Assign ${e.title}`}>Assign</Button>}
        </div>
      )}
    </article>
  );
}

// Rallies and meetings: what is coming up, and what each past one reached and signed up.
export default function Events({ campaign, role, onModal, mine }) {
  const events = useEvents(campaign.id);
  const [when, setWhen] = useState("Upcoming");
  const acts = role !== "candidate";
  const rows = (events.data || []).filter(WHEN[when]).sort((a, b) => {
    const [x, y] = [dayOf(a)?.getTime() ?? Infinity, dayOf(b)?.getTime() ?? Infinity];
    return when === "Upcoming" ? x - y : y - x;
  });
  const actions = acts ? <Button shape="rounded" onClick={() => onModal({ type: "event" })}>Schedule event</Button> : null;
  return (
    <>
      <WsHeader context={mine ? "My work" : "Field"} title={mine ? "My events" : "Events"} sub="Rallies and meetings, with mobilization counts." actions={actions} />
      <FilterPills label="When" options={Object.keys(WHEN)} value={when} onChange={setWhen} />
      {events.isLoading && <KitLoading />}
      {events.error && <KitError error={events.error} />}
      {events.data && (
        <section aria-label="Event list" className="flex flex-col gap-3">
          {rows.map((e) => (
            <EventCard key={e.id} event={e}
              onRecord={acts ? (ev) => onModal({ type: "record", event: ev }) : undefined}
              onInvite={acts ? (ev) => onModal({ type: "invite", event: ev }) : undefined}
              onQr={acts ? (ev) => onModal({ type: "qr", event: ev }) : undefined}
              onAssign={ASSIGNERS.includes(role) && !mine ? (ev) => onModal({ type: "assign-work", event: ev }) : undefined} />
          ))}
          {rows.length === 0 && <p className="text-muted-foreground">{when === "Upcoming" ? "Nothing planned yet." : "No past events yet."}</p>}
        </section>
      )}
    </>
  );
}
