// /counties: every published county branch, linking to its page.
import { Link } from "react-router-dom";
import { usePublicBranches } from "@/api/hooks";
import { Card } from "@/components/ui/card";
import PageHead from "./PageHead";
import { LoadingText } from "@/components/ui/loading-text";

const chairOf = (b) => b.officials.find((o) => o.office === "chair")?.name;

export default function Branches() {
  const branches = usePublicBranches();
  const list = branches.data || [];
  return (
    <div className="site-container py-12">
      <PageHead title="Counties" lead="Find your county branch: its officials, office and next meeting." />
      {branches.isLoading ? <LoadingText /> : null}
      {branches.isSuccess && !list.length ? <p className="text-muted-foreground">No branches are published yet.</p> : null}
      <div className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-4">
        {list.map((b) => (
          <Card key={b.county.id} asChild interactive>
            <Link to={`/counties/${b.county.id}`}>
              <span className="font-display text-card-title font-extrabold">{b.county.name}</span>
              {chairOf(b) ? <span className="text-ui text-muted-foreground">Chair: {chairOf(b)}</span> : null}
            </Link>
          </Card>
        ))}
      </div>
    </div>
  );
}
