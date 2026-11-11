import { Badge } from "@/components/ui/badge";
import { Card, CardTitle } from "@/components/ui/card";
import { formatNumber } from "@/lib/format";

/** How much is covered: `title`, the `count` line, then a red badge per gap (and `more` not shown), or `done`. */
export default function CoverageCard({ title, count, gaps, more = 0, done }) {
  return (
    <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Coverage">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <CardTitle>{title}</CardTitle>
        <span className="text-ui text-muted-foreground">{count}</span>
      </div>
      {gaps.length ? (
        <ul className="flex flex-wrap gap-2">
          {gaps.map(({ key, label, detail }) => (
            <li key={key} className="max-w-full">
              <Badge tone="bad" className="whitespace-normal">{label}{detail ? <span className="font-semibold opacity-80"> · {detail}</span> : null}</Badge>
            </li>
          ))}
          {more > 0 && <li className="text-small text-muted-foreground">and {formatNumber(more)} more</li>}
        </ul>
      ) : <p className="text-ui font-semibold text-primary">{done}</p>}
    </Card>
  );
}
