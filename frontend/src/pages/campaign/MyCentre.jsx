// An agent's own phone view: the centre they are readied for, how far they have come, and where
// their payments are.
import { Link } from "react-router-dom";
import { useAgents } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import WsHeader, { KitError, KitLoading } from "./WsHeader";

const STEPS = [["applied", "Applied"], ["vetted", "Vetted"], ["trained", "Trained"], ["ready", "Ready"]];

export default function MyCentre({ campaign }) {
  const agents = useAgents(campaign.id);
  const me = agents.data?.[0];
  const reached = me ? STEPS.findIndex(([key]) => key === me.status) : -1;
  return (
    <>
      <WsHeader context="My work" title="My centre" />
      {agents.isLoading && <KitLoading />}
      {agents.error && <KitError error={agents.error} />}
      {agents.data && !me && <p className="text-muted-foreground">You are not on this campaign's agent list yet.</p>}
      {me && (
        <div className="flex max-w-[560px] flex-col gap-4">
          <Card variant="outline" className="gap-2" role="region" aria-label="Your centre">
            <span className="text-ui text-muted-foreground">Registration centre</span>
            <span className="font-display text-[26px] leading-tight font-extrabold">{me.centre_name || "Not given yet"}</span>
            {me.ward_name && <span className="text-ui text-muted-foreground">{me.ward_name} ward</span>}
          </Card>
          <Card variant="outline" className="gap-3" role="region" aria-label="Your progress">
            <h2 className="text-card-title font-bold">Before polling day</h2>
            <ol className="flex flex-col gap-2">
              {STEPS.map(([key, label], i) => (
                <li key={key} className="flex items-center justify-between gap-3 border-t border-line-soft pt-2">
                  <span className={i <= reached ? "font-semibold" : "text-muted-foreground"}>{label}</span>
                  {i <= reached ? <Badge tone="ok">Done</Badge> : <Badge tone="stone">Not yet</Badge>}
                </li>
              ))}
            </ol>
            <p className="text-ui text-muted-foreground">Training: {me.training_date ? new Date(`${me.training_date}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" }) : "the campaign will tell you the date."}</p>
          </Card>
          <Card variant="outline" className="gap-2">
            <h2 className="text-card-title font-bold">Your details</h2>
            <p className="text-ui">{me.full_name} · <span className="tabular-nums">{me.phone}</span>{me.id_number ? <> · ID {me.id_number}</> : null}</p>
            <Link to="/campaign/mypayments" className="self-start font-bold">My payments</Link>
          </Card>
        </div>
      )}
    </>
  );
}
