// The console's reference data: boundary and voter register files, checked before they apply.
import { useState } from "react";
import { useImportRuns, useRunImport } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { ErrorText } from "@/components/ui/error-text";
import { formatDateTime } from "@/lib/format";

const KINDS = {
  boundaries: {
    title: "Boundaries",
    columns: "county_code, county_name, constituency_code, constituency_name, ward_code, ward_name, centre_code, centre_name",
    note: "One row per centre, or per ward with the centre columns blank. A file covers whole counties: a constituency, ward or centre it leaves out of a county it names is retired, hidden from pickers but kept for everything that refers to it.",
  },
  register: {
    title: "Voter register",
    columns: "county_code, ward_code, centre_code, registered_voters, turnout_pct",
    note: "A county row sets its voters and turnout; a ward row its voters; a ward and centre row the centre's voters. Targets keep their numbers until a campaign manager presses Refresh targets.",
  },
};
const TONE = { created: "ok", restored: "ok", renamed: "info", moved: "info", voters: "info", turnout: "info", retired: "warn" };

const readText = (file) => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve(String(reader.result));
  reader.onerror = () => reject(reader.error);
  reader.readAsText(file);
});

const summary = (counts) => Object.entries(counts).map(([k, n]) => `${n} ${k}`).join(", ") || "no changes";

function Report({ report }) {
  return (
    <div className="flex flex-col gap-2">
      <p role="status" className="font-semibold">
        {report.applied ? "Imported" : "This file would make"}: {summary(report.counts)} from {report.rows} rows.
      </p>
      {report.changes.length > 0 && (
        <div className="max-h-[320px] overflow-auto rounded-lg border border-line-soft">
          <Table stack minWidth={520} aria-label="Changes">
            <THead><TR><TH>Change</TH><TH>Level</TH><TH>Code</TH><TH>Detail</TH></TR></THead>
            <TBody>
              {report.changes.map((c, i) => (
                <TR key={i}>
                  <TD><Badge tone={TONE[c.change] || "stone"}>{c.change}</Badge></TD>
                  <TD>{c.level}</TD>
                  <TD className="tabular-nums">{c.code}</TD>
                  <TD className="text-muted-foreground">{c.detail}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function ImportCard({ kind }) {
  const { title, columns, note } = KINDS[kind];
  const run = useRunImport();
  const [file, setFile] = useState(null);  // { filename, csv }
  const [checked, setChecked] = useState(null);
  const pick = async (e) => {
    const chosen = e.target.files?.[0];
    run.reset();
    setChecked(null);
    setFile(chosen ? { filename: chosen.name, csv: await readText(chosen) } : null);
  };
  const check = () => run.mutate({ kind, ...file, dry_run: true }, { onSuccess: setChecked });
  const apply = () => run.mutate({ kind, ...file, dry_run: false });
  const report = run.data || checked;
  return (
    <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label={title}>
      <CardTitle>{title}</CardTitle>
      <p className="text-ui text-muted-foreground">{note}</p>
      <p className="text-small"><span className="font-semibold">Columns:</span> <code className="break-words">{columns}</code></p>
      <label className="flex flex-col gap-1.5 text-small font-semibold">
        CSV file
        <input type="file" accept=".csv,text/csv" onChange={pick} className="min-h-11 text-ui" />
      </label>
      <div className="flex flex-wrap gap-2">
        <Button variant="quiet" disabled={!file || run.isPending} onClick={check}>{run.isPending && !checked ? "Checking…" : "Check file"}</Button>
        <Button disabled={!checked || run.data?.applied || run.isPending} onClick={apply}>{run.isPending && checked ? "Importing…" : `Import ${title.toLowerCase()}`}</Button>
      </div>
      <ErrorText error={run.error} className="text-ui break-words" />
      {report && <Report report={report} />}
    </Card>
  );
}

function RecentImports() {
  const { data = [] } = useImportRuns();
  if (!data.length) return null;
  return (
    <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Recent imports">
      <CardTitle>Recent imports</CardTitle>
      <Table stack minWidth={520}>
        <THead><TR><TH>When</TH><TH>Kind</TH><TH>File</TH><TH>Changes</TH></TR></THead>
        <TBody>
          {data.map((r) => (
            <TR key={r.id}>
              <TD>{formatDateTime(r.created_at)}</TD>
              <TD className="capitalize">{r.kind}</TD>
              <TD>{r.filename || "Unnamed"}</TD>
              <TD className="text-muted-foreground">{summary(r.counts)}</TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </Card>
  );
}

export default function ReferenceData() {
  return (
    <div className="kit flex flex-col gap-4">
      <p className="text-ui text-muted-foreground">Check a file first: it reports every change and writes nothing. One bad row and the import changes nothing at all. The same imports run from the server with <code>campaign-crm import-boundaries</code> and <code>campaign-crm import-register</code>.</p>
      <ImportCard kind="boundaries" />
      <ImportCard kind="register" />
      <RecentImports />
    </div>
  );
}
