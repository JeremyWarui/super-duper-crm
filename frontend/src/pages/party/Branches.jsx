// The superuser's county branches: officials, office and next meeting, and whether each is public.
import { useState } from "react";
import { useAdminBranches, useSaveBranch } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, KpiValue } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { RowButton, TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";

const FIELDS = [
  ["chairperson", "Chairperson"],
  ["secretary", "Secretary"],
  ["office_address", "Office address"],
  ["phone", "Office phone"],
  ["email", "Office email"],
  ["next_meeting_venue", "Next meeting venue"],
];

const formOf = (branch) => ({
  ...Object.fromEntries(FIELDS.map(([key]) => [key, branch?.[key] ?? ""])),
  next_meeting_on: branch?.next_meeting_on ?? "",
  published: branch?.published ?? false,
});

function BranchForm({ row, onDone }) {
  const save = useSaveBranch();
  const [form, setForm] = useState(() => formOf(row.branch));
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const submit = (e) => {
    e.preventDefault();
    save.mutate({ county: row.county.id, ...form, next_meeting_on: form.next_meeting_on || null }, { onSuccess: onDone });
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-3.5">
      <h2 className="text-card-title font-bold">{row.county.name} branch</h2>
      {FIELDS.map(([key, label]) => (
        <Field key={key} label={label}>
          <Input value={form[key]} onChange={set(key)} maxLength={key === "office_address" ? 300 : key === "phone" ? 20 : key === "email" ? 254 : 150} type={key === "email" ? "email" : "text"} />
        </Field>
      ))}
      <Field label="Next meeting date">
        <Input type="date" value={form.next_meeting_on} onChange={set("next_meeting_on")} />
      </Field>
      <label className="flex min-h-11 items-center gap-2.5 text-body">
        <input type="checkbox" className="size-[18px] accent-primary" checked={form.published} onChange={set("published")} />
        Show this branch on the website
      </label>
      {save.error ? <p role="alert" className="text-small font-semibold text-destructive">{save.error.message}</p> : null}
      <div className="flex flex-wrap gap-2.5">
        <Button type="submit" shape="rounded" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save branch"}</Button>
        <Button type="button" shape="rounded" variant="quiet" onClick={onDone}>Close</Button>
      </div>
    </form>
  );
}

export default function Branches() {
  const rows = useAdminBranches();
  const [open, setOpen] = useState(null);
  if (rows.isLoading) return <p className="text-muted-foreground">Loading…</p>;
  if (rows.error) return <p role="alert">{rows.error.message}</p>;
  const list = rows.data;
  const withBranch = list.filter((r) => r.branch);
  const published = withBranch.filter((r) => r.branch.published).length;
  const chaired = withBranch.filter((r) => r.branch.chairperson).length;
  const current = list.find((r) => r.county.id === open);

  return (
    <>
      <section aria-label="Summary" className="grid grid-cols-[repeat(auto-fit,minmax(190px,1fr))] gap-4">
        <Card variant="tile"><span className="text-ui font-semibold text-muted-foreground">County branches</span><KpiValue>{withBranch.length} / {list.length}</KpiValue><span className="text-small text-muted-foreground">set up</span></Card>
        <Card variant="tile"><span className="text-ui font-semibold text-muted-foreground">On the website</span><KpiValue>{published}</KpiValue><span className="text-small text-muted-foreground">published</span></Card>
        <Card variant="tile"><span className="text-ui font-semibold text-muted-foreground">Chairpersons</span><KpiValue>{chaired}</KpiValue><span className="text-small text-muted-foreground">named</span></Card>
      </section>
      <div className="flex flex-wrap items-start gap-6">
        <Card variant="outline" className="min-w-0 flex-[3_1_520px] gap-3.5">
          <h2 className="text-card-title font-bold">County branches</h2>
          <Table minWidth={640}>
            <THead>
              <TR><TH>County</TH><TH>Chairperson</TH><TH>Secretary</TH><TH>Next meeting</TH><TH>Status</TH></TR>
            </THead>
            <TBody>
              {list.map((r) => (
                <TR key={r.county.id} selected={r.county.id === open}>
                  <TD><RowButton onClick={() => setOpen(r.county.id)}>{r.county.name}</RowButton></TD>
                  <TD>{r.branch?.chairperson || "—"}</TD>
                  <TD>{r.branch?.secretary || "—"}</TD>
                  <TD>{r.branch?.next_meeting_on || "—"}</TD>
                  <TD>
                    {r.branch ? (
                      <Badge tone={r.branch.published ? "ok" : "warn"}>{r.branch.published ? "Published" : "Draft"}</Badge>
                    ) : (
                      <Badge tone="stone">Not set up</Badge>
                    )}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </Card>
        {current ? (
          <Card variant="outline" className="flex-[2_1_320px]">
            <BranchForm key={current.county.id} row={current} onDone={() => setOpen(null)} />
          </Card>
        ) : null}
      </div>
    </>
  );
}
