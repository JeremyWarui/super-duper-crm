// The console's Export tab: the whole installation's data as one zip, for the buyer's records.
import { useState } from "react";
import { download } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { nairobiDate } from "@/lib/format";
import { ErrorText } from "@/components/ui/error-text";
import { StatusText } from "@/components/ui/notice";

export default function ExportPanel() {
  const [state, setState] = useState({ busy: false, error: null, done: false });
  const run = () => {
    setState({ busy: true, error: null, done: false });
    download("/admin/export/", `export-${nairobiDate()}.zip`)
      .then(() => setState({ busy: false, error: null, done: true }))
      .catch((e) => setState({ busy: false, error: e.message, done: false }));
  };
  return (
    <div className="kit">
      <Card variant="outline" className="gap-3" role="region" aria-label="Export">
        <CardTitle>Export everything</CardTitle>
        <p className="text-ui">
          Every table as JSON and CSV in one zip, with a manifest of what is inside: for your own records, or to move to another
          provider. Passwords and sign-in links are left out, so logins that should move with you need a backup instead. Each
          export is recorded in the audit trail.
        </p>
        <p className="text-ui text-muted-foreground">
          On the server: <code>campaign-crm export</code>. For a full copy you can restore, use <code>campaign-crm backup</code>.
        </p>
        <Button loading={state.busy} className="self-start" disabled={state.busy} onClick={run}>{state.busy ? "Preparing…" : "Download export"}</Button>
        {state.done && <StatusText>Downloaded.</StatusText>}
        <ErrorText error={state.error} className="text-ui" />
      </Card>
    </div>
  );
}
