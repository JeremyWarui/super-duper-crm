// County branches: their officials, kept as terms by the Membership Officer, and for the
// superuser the office, next meeting and whether each branch is public.
import { useState } from "react";
import {
  useAppointOfficial, useBranchOfficials, useEndTerm, useOfficeBranches, usePartyMembers, useSaveBranch, useUploadMinutes,
} from "@/api/hooks";
import { useAuth } from "@/store/auth";
import ConfigFields from "@/components/ConfigFields";
import MemberSearch from "@/components/MemberSearch";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { StatTiles } from "@/components/ui/stat-tiles";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input, NativeSelect } from "@/components/ui/input";
import { RowButton, TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { formatDate, nairobiDate } from "../../lib/format";
import { ErrorText } from "@/components/ui/error-text";
import { useShowMore } from "@/lib/useShowMore";
import { LoadMore } from "@/components/ui/load-more";
import { LoadingText } from "@/components/ui/loading-text";

const FIELDS = [
  ["office_address", "Office address", 300],
  ["phone", "Office phone", 20],
  ["email", "Office email", 254, { type: "email" }],
  ["next_meeting_venue", "Next meeting venue", 150],
];
const OFFICES = [
  ["chair", "Chairperson"],
  ["secretary", "Secretary"],
  ["treasurer", "Treasurer"],
  ["organising_secretary", "Organising secretary"],
  ["youth_leader", "Youth leader"],
  ["women_leader", "Women leader"],
  ["other", "Other office"],
];
const STARTS = [["elected", "Elected at a branch meeting"], ["interim", "Interim appointment"]];
const ENDS = [["resigned", "Resigned"], ["removed", "Removed"], ["completed", "Term completed"]];
const END_LABEL = { replaced: "Replaced", resigned: "Resigned", removed: "Removed", completed: "Term completed" };

const holderOf = (branch, office) => branch?.officials?.find((o) => o.office === office)?.name;

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
    <form onSubmit={submit} className="flex flex-col gap-3.5 border-t border-line-soft pt-4" aria-label="Branch office">
      <h3 className="text-card-title font-bold">Branch office</h3>
      <ConfigFields fields={FIELDS} form={form} set={set} />
      <Field label="Next meeting date">
        <Input type="date" value={form.next_meeting_on} onChange={set("next_meeting_on")} />
      </Field>
      <label className="flex min-h-11 items-center gap-2.5 text-body">
        <input type="checkbox" className="size-[18px] accent-primary" checked={form.published} onChange={set("published")} />
        Show this branch on the website
      </label>
      <ErrorText error={save.error} className="text-small" />
      <Button type="submit" shape="rounded" className="self-start" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save branch"}</Button>
    </form>
  );
}

function EndTerm({ term, onDone }) {
  const end = useEndTerm();
  const [form, setForm] = useState({ term_end: nairobiDate(), end_reason: "resigned" });
  return (
    <form className="flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); end.mutate({ id: term.id, ...form }, { onSuccess: onDone }); }}>
      <Field label="Last day"><Input type="date" value={form.term_end} min={term.term_start} onChange={(e) => setForm({ ...form, term_end: e.target.value })} /></Field>
      <Field label="Why">
        <NativeSelect value={form.end_reason} onChange={(e) => setForm({ ...form, end_reason: e.target.value })}>
          {ENDS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </NativeSelect>
      </Field>
      <Button type="submit" shape="rounded" variant="danger" size="sm" disabled={end.isPending}>End the term</Button>
      <Button type="button" shape="rounded" variant="ghost" size="sm" onClick={onDone}>Keep</Button>
      <ErrorText error={end.error} className="w-full text-small" />
    </form>
  );
}

function OfficeBox({ label, term, next, onEnd, ending }) {
  const tag = term?.lapsed ? <Badge tone="bad">Membership lapsed</Badge> : term ? <Badge tone="ok">In office</Badge> : next ? <Badge tone="warn">Starts {formatDate(next.term_start)}</Badge> : <Badge tone="bad">Vacant</Badge>;
  return (
    <div className={cn("flex flex-col gap-2 rounded-xl border-[1.5px] p-3.5", term ? "border-line-soft bg-ground-app" : "border-[#F1DE9A] bg-[#FFFBEA]")} role="group" aria-label={label}>
      <div className="flex items-center justify-between gap-2">
        <span className="font-bold">{label}</span>
        {tag}
      </div>
      {term ? (
        <>
          <span className="text-ui">
            <strong>{term.holder_name}</strong> since {formatDate(term.term_start)}{term.term_end ? `, until ${formatDate(term.term_end)}` : ""}
            {!term.member && <span className="block text-small text-warn-foreground">{term.note || "Not linked to a member."}</span>}
            {term.lapsed && <span className="block text-small text-bad-foreground">No longer an approved member, so the website no longer names them. End the term and appoint someone.</span>}
          </span>
          {ending ? onEnd(term) : <Button shape="rounded" size="sm" variant="quiet" className="self-start" onClick={() => onEnd(term, true)} aria-label={`End the ${label.toLowerCase()}'s term`}>End term</Button>}
        </>
      ) : next ? <span className="text-ui">{next.holder_name}</span> : null}
    </div>
  );
}

function Appoint({ county }) {
  const appoint = useAppointOfficial();
  const uploadMinutes = useUploadMinutes();
  const blank = { office: "chair", title: "", member: null, start_reason: "elected", term_start: nairobiDate(), note: "", minutes: null };
  const [form, setForm] = useState(blank);
  const [q, setQ] = useState("");
  const found = usePartyMembers({ q, status: "approved", county: county.id });
  const searching = q.trim().length >= 2;
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));
  const pickFile = (e) => {
    const file = e.target.files?.[0];
    if (file) uploadMinutes.mutate(file, { onSuccess: (m) => set({ minutes: m }) });
  };
  const submit = (e) => {
    e.preventDefault();
    appoint.mutate(
      {
        county: county.id, office: form.office, title: form.title, member: form.member.id, term_start: form.term_start,
        start_reason: form.start_reason, note: form.note, minutes_file: form.minutes?.id ?? null,
      },
      { onSuccess: () => { setForm(blank); setQ(""); } },
    );
  };
  const ready = form.member && form.term_start && (form.office !== "other" || form.title.trim());
  return (
    <form onSubmit={submit} className="flex flex-col gap-3 border-t border-line-soft pt-4" aria-label="Appoint an official">
      <h3 className="text-card-title font-bold">Appoint</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Office">
          <NativeSelect value={form.office} onChange={(e) => set({ office: e.target.value })}>
            {OFFICES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </NativeSelect>
        </Field>
        {form.office === "other" && <Field label="Office name"><Input value={form.title} maxLength={80} onChange={(e) => set({ title: e.target.value })} /></Field>}
        <Field label="Reason">
          <NativeSelect value={form.start_reason} onChange={(e) => set({ start_reason: e.target.value })}>
            {STARTS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </NativeSelect>
        </Field>
        <Field label="Effective from"><Input type="date" value={form.term_start} onChange={(e) => set({ term_start: e.target.value })} /></Field>
      </div>
      <MemberSearch
        label="Member"
        hint={`Approved members in ${county.name}; type two or more letters of a name or phone.`}
        query={q}
        onQuery={setQ}
        results={searching ? found.data?.items || [] : undefined}
        loading={found.isFetching}
        error={searching && found.error}
        empty={`No approved member in ${county.name} matches.`}
        picked={form.member}
        onPick={(m) => set({ member: m })}
      />
      <label className="flex flex-col gap-1.5 text-small font-semibold">
        Signed minutes of the meeting
        <input type="file" accept="application/pdf,image/jpeg,image/png,image/webp" onChange={pickFile} className="min-h-11 text-ui font-normal" />
        <span className="font-normal text-muted-foreground">{uploadMinutes.isPending ? "Uploading…" : form.minutes ? `Attached: ${form.minutes.name}` : "A PDF or a photo; kept private to the party office."}</span>
      </label>
      <ErrorText error={uploadMinutes.error} className="text-small" />
      <Field label="Note"><Input value={form.note} maxLength={1000} onChange={(e) => set({ note: e.target.value })} /></Field>
      <ErrorText error={appoint.error} className="text-small" />
      <Button type="submit" shape="rounded" className="self-start" disabled={!ready || appoint.isPending || uploadMinutes.isPending}>
        {appoint.isPending ? "Saving…" : "Appoint"}
      </Button>
      <p className="text-small text-muted-foreground">Appointing someone ends the current holder's term the day before. Every change is recorded in the audit trail.</p>
    </form>
  );
}

function Officials({ county }) {
  const { data, isLoading, error } = useBranchOfficials(county.id);
  const [ending, setEnding] = useState(null);
  const past = useShowMore(data?.history);
  if (isLoading) return <LoadingText />;
  if (error) return <ErrorText error={error} />;
  const others = data.current.filter((t) => t.office === "other");
  const onEnd = (term, open) => (open ? setEnding(term.id) : <EndTerm term={term} onDone={() => setEnding(null)} />);
  return (
    <section className="flex flex-col gap-4" aria-label="Officials">
      <h3 className="text-card-title font-bold">Officials</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        {OFFICES.filter(([o]) => o !== "other").map(([office, label]) => (
          <OfficeBox key={office} label={label}
            term={data.current.find((t) => t.office === office)}
            next={data.upcoming.find((t) => t.office === office)}
            ending={ending && data.current.find((t) => t.office === office)?.id === ending} onEnd={onEnd} />
        ))}
        {others.map((t) => <OfficeBox key={t.id} label={t.label} term={t} ending={ending === t.id} onEnd={onEnd} />)}
      </div>
      <Appoint county={county} />
      {data.history.length > 0 && (
        <details className="border-t border-line-soft pt-3">
          <summary className="min-h-11 cursor-pointer content-center font-bold">Past officials ({data.history.length})</summary>
          <ul className="mt-2 flex flex-col">
            {past.visible.map((t) => (
              <li key={t.id} className="flex flex-wrap justify-between gap-2 border-t border-line-soft py-2 text-ui">
                <span><strong>{t.holder_name}</strong>, {t.label}</span>
                <span className="text-muted-foreground">{formatDate(t.term_start)} to {formatDate(t.term_end)} · {END_LABEL[t.end_reason] || "Ended"}</span>
              </li>
            ))}
          </ul>
          <LoadMore shown={past.shown} total={past.total} noun="past officials" hasMore={past.hasMore} onMore={past.more} />
        </details>
      )}
    </section>
  );
}

export default function Branches() {
  const rows = useOfficeBranches();
  const superuser = useAuth((s) => s.user?.is_superuser);
  const [open, setOpen] = useState(null);
  const counties = useShowMore(rows.data);
  if (rows.isLoading) return <LoadingText />;
  if (rows.error) return <ErrorText error={rows.error} />;
  const list = rows.data;
  const withBranch = list.filter((r) => r.branch);
  const published = withBranch.filter((r) => r.branch.published).length;
  const chaired = withBranch.filter((r) => holderOf(r.branch, "chair")).length;
  const current = list.find((r) => r.county.id === open);

  return (
    <>
      <StatTiles tiles={[
        ["County branches", `${withBranch.length} / ${list.length}`, "set up"],
        ["On the website", published, "published"],
        ["Chairpersons", chaired, "in office"],
      ]} />
      <Card variant="outline" className="min-w-0 gap-3.5">
        <h2 className="text-card-title font-bold">County branches</h2>
        <Table stack minWidth={640}>
          <THead>
            <TR><TH>County</TH><TH>Chairperson</TH><TH>Secretary</TH><TH>Next meeting</TH><TH>Status</TH></TR>
          </THead>
          <TBody>
            {counties.visible.map((r) => (
              <TR key={r.county.id}>
                <TD><RowButton onClick={() => setOpen(r.county.id)}>{r.county.name}</RowButton></TD>
                <TD>{holderOf(r.branch, "chair") || "Vacant"}</TD>
                <TD>{holderOf(r.branch, "secretary") || "Vacant"}</TD>
                <TD>{r.branch?.next_meeting_on || "None set"}</TD>
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
        <LoadMore shown={counties.shown} total={counties.total} noun="counties" hasMore={counties.hasMore} onMore={counties.more} />
      </Card>
      {current ? (
        <Dialog
          key={current.county.id}
          title={`${current.county.name} County`}
          description="Only approved members hold an office; each has one holder at a time."
          onClose={() => setOpen(null)}
          className="w-[min(760px,calc(100vw-32px))]"
        >
          <Officials county={current.county} />
          {superuser && <BranchForm row={current} onDone={() => setOpen(null)} />}
        </Dialog>
      ) : null}
    </>
  );
}
