// The console's Export tab: the whole installation's data as one zip, for the buyer's records.
import { useState } from "react";
import { download } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export default function ExportPanel() {
  const [state, setState] = useState({ busy: false, error: null, done: false });
  const run = () => {
    setState({ busy: true, error: null, done: false });
    download("/admin/export/", `export-${new Date().toISOString().slice(0, 10)}.zip`)
      .then(() => setState({ busy: false, error: null, done: true }))
      .catch((e) => setState({ busy: false, error: e.message, done: false }));
  };
  return (
    <div className="kit">
      <Card variant="outline" className="gap-3" role="region" aria-label="Export">
        <h2 className="text-card-title font-bold">Export everything</h2>
        <p className="text-ui">
          Every table as JSON and CSV in one zip, with a manifest of what is inside: for your own records, or to move to another
          provider. Passwords and sign-in links are left out, so logins that should move with you need a backup instead. Each
          export is recorded in the audit trail.
        </p>
        <p className="text-ui text-muted-foreground">
          On the server: <code>campaign-crm export</code>. For a full copy you can restore, use <code>campaign-crm backup</code>.
        </p>
        <Button shape="rounded" className="self-start" disabled={state.busy} onClick={run}>{state.busy ? "Preparing…" : "Download export"}</Button>
        {state.done && <p role="status" className="text-ui font-semibold text-primary">Downloaded.</p>}
        {state.error && <p role="alert" className="text-ui font-semibold text-destructive">{state.error}</p>}
      </Card>
    </div>
  );
}
