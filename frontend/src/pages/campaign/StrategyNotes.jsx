import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

// The strategy read: what the campaign's own numbers say to do next.
export default function StrategyNotes({ notes, wide = true }) {
  return (
    <Card variant="outline" className={cn("min-w-0 gap-3", !wide && "max-w-[760px]")} aria-labelledby="strategy-h" role="region">
      <div className="flex flex-col gap-1">
        <h2 id="strategy-h" className="text-card-title font-bold">Strategy read</h2>
        <p className="text-ui text-muted-foreground">Computed from your targets, events and mobilizers.</p>
      </div>
      {(notes || []).map((n) => (
        <div key={n.title} className={cn("flex flex-col gap-0.5 border-l-4 py-1 pl-3", n.tone === "go" ? "border-primary" : "border-accent")}>
          <span className="font-semibold">{n.title}</span>
          <span className="text-ui text-text-2">{n.text}</span>
        </div>
      ))}
      {!notes?.length && <p className="text-ui text-muted-foreground">No flags right now: coverage looks balanced.</p>}
    </Card>
  );
}
