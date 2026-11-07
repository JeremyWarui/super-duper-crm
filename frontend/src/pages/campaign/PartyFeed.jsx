// A hosted workspace's "From the party" page: party events and notices for the area, member
// counts per ward, and the counts the candidate chooses to share back.
import { useState } from "react";
import { useChangeSharing, usePartyFeed } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { formatDate, formatNumber as fmt } from "@/lib/format";
import { cn } from "@/lib/utils";
import WsHeader, { KitLoading } from "./WsHeader";
import { ErrorText } from "@/components/ui/error-text";

const SWITCHES = [
  ["event_reach", "Event reach summary", "Totals reached and attended at your events"],
  ["ward_coverage", "Coverage map", "Which wards have mobilizers"],
  ["supporter_counts", "Supporter counts by ward", "Numbers only, no names"],
];
const LABEL = Object.fromEntries(SWITCHES.map(([k, l]) => [k, l]));
const FILTERS = ["All", "Events", "Members", "Notices"];

export default function PartyFeed({ campaign }) {
  const page = usePartyFeed(campaign.id);
  const data = page.data;
  return (
    <>
      <WsHeader context="Reach out" title="Party feed & sharing" sub="What the party shares with you, and what you share back." />
      {page.isLoading && <KitLoading />}
      <ErrorText error={page.error} />
      {data && (
        <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
          <Feed data={data} />
          <Sharing campaign={campaign} data={data} />
        </div>
      )}
    </>
  );
}

function Feed({ data }) {
  const [filter, setFilter] = useState("All");
  const members = data.members_by_ward.reduce((n, w) => n + w.count, 0);
  const show = (kind) => filter === "All" || filter === kind;
  const empty = !data.events.length && !data.notices.length && !members;
  return (
    <Card className="min-w-0 gap-4 p-5" role="region" aria-label="From the party">
      <h2 className="font-display text-card-title font-extrabold">From the party</h2>
      <div className="flex flex-wrap gap-2" role="group" aria-label="Show">
        {FILTERS.map((f) => (
          <button key={f} type="button" aria-pressed={filter === f} onClick={() => setFilter(f)}
            className={cn("min-h-10 rounded-full border px-4 text-small font-semibold", filter === f ? "border-ink bg-ink text-on-dark" : "border-line bg-card")}>
            {f}
          </button>
        ))}
      </div>
      {empty && <p className="text-muted-foreground">Nothing from the party for your area yet.</p>}
      <ul className="flex flex-col">
        {show("Events") && data.events.map((e) => (
          <Item key={e.id} kind="Event" when={formatDate(e.event_date)} title={e.title} body={[e.venue, e.body].filter(Boolean).join(" · ")} />
        ))}
        {show("Members") && members > 0 && (
          <Item kind="Members" when="now" title={`${fmt(members)} approved party members in your area`}
            body={data.members_by_ward.filter((w) => w.count).map((w) => `${w.ward} ${fmt(w.count)}`).join(" · ") + ". Counts only; member contacts are not shared with campaigns."} />
        )}
        {show("Notices") && data.notices.map((n) => (
          <Item key={n.id} kind="Notice" when={formatDate(n.published_on)} title={n.title} body={n.body} />
        ))}
      </ul>
    </Card>
  );
}

function Item({ kind, when, title, body }) {
  return (
    <li className="flex flex-col gap-1 border-b border-line py-3 last:border-0">
      <span className="text-meta font-semibold uppercase text-muted-foreground">{kind} · {when}</span>
      <strong>{title}</strong>
      {body && <p className="line-clamp-3 text-muted-foreground">{body}</p>}
    </li>
  );
}

function Sharing({ campaign, data }) {
  const change = useChangeSharing(campaign.id);
  const on = data.sharing;
  const flip = (key) => change.mutate({ ...on, [key]: !on[key] });
  const seen = SWITCHES.filter(([k]) => on[k]).map(([, l]) => l);
  return (
    <Card className="min-w-0 content-start gap-4 p-5" role="region" aria-label="Sharing and privacy">
      <h2 className="font-display text-card-title font-extrabold">Sharing & privacy</h2>
      {!data.can_change && <p className="text-small text-muted-foreground">Only the candidate changes what the campaign shares.</p>}
      <ul className="flex flex-col gap-3">
        {SWITCHES.map(([key, label, hint]) => (
          <li key={key} className="flex items-center justify-between gap-3">
            <span><strong>{label}</strong><br /><span className="text-small text-muted-foreground">{hint}</span></span>
            <Toggle label={label} checked={on[key]} disabled={!data.can_change || change.isPending} onClick={() => flip(key)} />
          </li>
        ))}
        <li className="flex items-center justify-between gap-3">
          <span><strong>Supporter list</strong><br /><span className="text-small text-muted-foreground">Always stays with your campaign</span></span>
          <Toggle label="Supporter list" checked={false} disabled />
        </li>
      </ul>
      <ErrorText error={change.error} />
      <div className="flex flex-col gap-1 rounded-lg bg-muted p-4">
        <h3 className="font-bold">What the party sees right now</h3>
        {seen.length ? seen.map((s) => <span key={s}>• {s}</span>) : <span className="text-muted-foreground">Nothing. Every share is off.</span>}
      </div>
      <div className="flex flex-col gap-1">
        <h3 className="font-bold">Sharing history</h3>
        {data.history.length === 0 && <span className="text-muted-foreground">No changes yet.</span>}
        {data.history.map((h, i) => (
          <span key={i} className="text-small">{formatDate(h.at)} · {LABEL[h.switch]} turned {h.on ? "on" : "off"} by {h.by}</span>
        ))}
      </div>
      <Badge tone="info" className="self-start">Counts only, never names or phones</Badge>
    </Card>
  );
}

function Toggle({ label, checked, disabled, onClick }) {
  return (
    <button type="button" role="switch" aria-checked={checked} aria-label={label} disabled={disabled} onClick={onClick}
      className={cn("flex h-7 w-[50px] shrink-0 rounded-full p-[3px] transition-colors disabled:cursor-not-allowed",
        checked ? "justify-end bg-primary" : "justify-start bg-muted-foreground", disabled && !checked && "bg-line")}>
      <span className="size-[22px] rounded-full bg-white" />
    </button>
  );
}
