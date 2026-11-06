// The line over every page of a campaign closed after the election.
import { Card } from "@/components/ui/card";

export default function ClosedNote() {
  return (
    <Card variant="tile" role="status" className="bg-stone text-ui font-semibold">
      This campaign is closed: it is read-only.
    </Card>
  );
}
