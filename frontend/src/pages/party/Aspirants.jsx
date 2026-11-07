// The nominations officer's page: nominate approved members, move nominations, create workspaces.
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  useAspirant,
  useAspirants,
  useCandidates,
  useCreateWorkspace,
  useDraftNominationWindow,
  useMarkNominationFeePaid,
  useMoveAspirant,
  useNominate,
  useNominationWindows,
  usePartyPlaceLists,
  usePublishNominationWindow,
  useReviseNominationWindow,
} from "@/api/hooks";
import { SlottedHeader } from "@/components/layout/AppPage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { ErrorText } from "@/components/ui/error-text";
import { FilterSelect, Field, Input, NativeSelect, Textarea } from "@/components/ui/input";
import { FormActions } from "@/components/ui/form-actions";
import { InviteDialog } from "@/components/ui/invite-dialog";
import { LoadingText } from "@/components/ui/loading-text";
import { Pager } from "@/components/ui/pager";
import { RowButton, TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { isEmail } from "@/lib/email";
import { formatDate, formatKES } from "@/lib/format";
import { useAuth } from "@/store/auth";
import { ASPIRANT_MOVES, ASPIRANT_STATUS_LABEL, ASPIRANT_STATUS_TONE, NEEDS_REASON, PAGE_SIZE, SEAT_AREA, SEAT_LABEL, SEATS } from "./helpers";

// County, then constituency, then ward, down to the level the seat is fought over.
function AreaPicker({ level, area, setArea }) {
  const { counties, constituencies, wards } = usePartyPlaceLists(area);
  return (
    <div className="flex flex-wrap gap-2">
      <FilterSelect
        label="County"
        blank="Pick the county"
        value={area.county}
        options={counties}
        onChange={(county) => setArea({ county, constituency: "", ward: "" })}
      />
      {level !== "county" && (
        <FilterSelect
          label="Constituency"
          blank="Pick the constituency"
          value={area.constituency}
          options={constituencies}
          disabled={!area.county}
          onChange={(constituency) => setArea({ ...area, constituency, ward: "" })}
        />
      )}
      {level === "ward" && (
        <FilterSelect
          label="Ward"
          blank="Pick the ward"
          value={area.ward}
          options={wards}
          disabled={!area.constituency}
          onChange={(ward) => setArea({ ...area, ward })}
        />
      )}
    </div>
  );
}

function Nominate({ onClose }) {
  const [q, setQ] = useState("");
  const [member, setMember] = useState(null);
  const [seat, setSeat] = useState("mca");
  const [area, setArea] = useState({ county: "", constituency: "", ward: "" });
  const candidates = useCandidates(q);
  const nominate = useNominate();
  const level = SEAT_AREA[seat];
  const ready = member && area[level];

  const submit = () =>
    nominate.mutate(
      { member: member.id, seat, [level]: area[level] },
      { onSuccess: onClose },
    );

  return (
    <Dialog title="Nominate a member" description="Only approved members without a live nomination are offered." onClose={onClose}>
      {member ? (
        <Card variant="tinted" className="items-start gap-2">
          <span className="font-semibold">{member.full_name}</span>
          <span className="text-ui text-muted-foreground">{member.ward.name}</span>
          <Button shape="rounded" variant="quiet" size="sm" onClick={() => { setMember(null); nominate.reset(); }}>Choose someone else</Button>
        </Card>
      ) : (
        <>
          <Input
            aria-label="Find a member"
            placeholder="Name, or their whole phone number"
            maxLength={100}
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <ErrorText error={candidates.error} />
          {candidates.data && <div className="flex flex-col items-start">
            {candidates.data.map((c) => (
              <Button key={c.id} shape="rounded" variant="link" className="min-h-11" onClick={() => { setMember(c); nominate.reset(); }}>
                {c.full_name} · {c.ward.name}
              </Button>
            ))}
            {candidates.isSuccess && candidates.data.length === 0 && (
              <p className="text-ui text-muted-foreground">No approved member matches.</p>
            )}
          </div>}
        </>
      )}
      <NativeSelect
        aria-label="Seat"
        value={seat}
        onChange={(e) => { setSeat(e.target.value); setArea({ county: "", constituency: "", ward: "" }); }}
      >
        {SEATS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </NativeSelect>
      <AreaPicker level={level} area={area} setArea={setArea} />
      <ErrorText error={nominate.error} className="text-small" />
      <FormActions>
        <Button shape="rounded" variant="quiet" onClick={onClose}>Cancel</Button>
        <Button shape="rounded" disabled={!ready || nominate.isPending} onClick={submit}>
          {nominate.isPending ? "Nominating…" : "Nominate"}
        </Button>
      </FormActions>
    </Dialog>
  );
}

function Workspace({ aspirant, onDone }) {
  const create = useCreateWorkspace();
  const memberEmail = aspirant.member.email || "";
  const [form, setForm] = useState({ title: "", election_date: "", candidate: "", candidate_email: memberEmail, manager: "", manager_email: "" });
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  const submit = () =>
    create.mutate(
      {
        id: aspirant.id,
        candidate: { username: form.candidate.trim(), email: form.candidate_email.trim() },
        ...(form.manager.trim() ? { manager: { username: form.manager.trim(), email: form.manager_email.trim() } } : {}),
        ...(form.title.trim() ? { title: form.title.trim() } : {}),
        ...(form.election_date ? { election_date: form.election_date } : {}),
      },
      { onSuccess: (made) => onDone(made.logins) },
    );

  return (
    <div className="flex flex-col gap-3 border-t border-line-soft pt-4">
      <div className="flex flex-col gap-0.5">
        <h3 className="text-card-title font-bold">Create the campaign workspace</h3>
        <p className="text-ui text-muted-foreground">
          It is built on the {SEAT_LABEL[aspirant.seat]} seat for {aspirant.area.name}.
        </p>
      </div>
      <Input aria-label="Campaign title" maxLength={150}
        placeholder={`${aspirant.member.full_name} for ${SEAT_LABEL[aspirant.seat]}`}
        value={form.title} onChange={set("title")} />
      <Input aria-label="Election date" type="date"
        value={form.election_date} onChange={set("election_date")} />
      <Input aria-label="Aspirant's username" maxLength={150}
        placeholder="The aspirant's new username" value={form.candidate} onChange={set("candidate")} />
      <Input aria-label="Aspirant's email" type="email" maxLength={254}
        placeholder="The aspirant's email, to sign in with" value={form.candidate_email} onChange={set("candidate_email")} />
      {memberEmail && form.candidate_email.trim().toLowerCase() === memberEmail.toLowerCase() ? (
        <p className="text-small text-muted-foreground">Their member login moves to this one: they sign in once and see both the workspace and their membership.</p>
      ) : null}
      <Input aria-label="Manager's username" maxLength={150}
        placeholder="A manager's new username (optional)" value={form.manager} onChange={set("manager")} />
      {form.manager.trim() ? (
        <Input aria-label="Manager's email" type="email" maxLength={254}
          placeholder="The manager's email, to sign in with" value={form.manager_email} onChange={set("manager_email")} />
      ) : null}
      <ErrorText error={create.error} className="text-small" />
      <FormActions>
        <Button shape="rounded" disabled={form.candidate.trim().length < 3 || !isEmail(form.candidate_email) || (form.manager.trim() && !isEmail(form.manager_email)) || create.isPending} onClick={submit}>
          {create.isPending ? "Creating…" : "Create workspace"}
        </Button>
      </FormActions>
    </div>
  );
}

function Detail({ row, onClose }) {
  const detail = useAspirant(row.id);
  const move = useMoveAspirant();
  const [reason, setReason] = useState("");
  const [logins, setLogins] = useState(null);
  const a = detail.data || row;
  const actions = ASPIRANT_MOVES[a.status] || [];

  if (logins?.length) {
    const [first, ...rest] = logins;
    return (
      <InviteDialog
        title={first.role === "candidate" ? "The aspirant's login" : "The campaign manager's login"}
        invite={first.invite}
        username={first.username}
        onClose={() => setLogins(rest.length ? rest : null)}
      />
    );
  }

  return (
    <Dialog title={a.member.full_name} description={`${SEAT_LABEL[a.seat]} · ${a.area.name}`} onClose={onClose}>
      <div className="flex flex-col gap-1.5 text-ui text-muted-foreground">
        <div><Badge tone={ASPIRANT_STATUS_TONE[a.status]}>{ASPIRANT_STATUS_LABEL[a.status]}</Badge></div>
        <div>Nominated: {formatDate(a.created_at)}</div>
        <div>Decided: {formatDate(a.decided_at)}</div>
        {a.status_reason && <div>Reason: {a.status_reason}</div>}
        <div>Workspace: {a.campaign_id ? "created" : "none yet"}</div>
      </div>
      {a.window_title && <Application a={a} />}
      <ErrorText error={detail.error} />
      {actions.length > 0 && (
        <>
          <Input
            aria-label="Reason"
            placeholder="Reason (needed to reject or suspend)"
            maxLength={1000}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <FormActions>
            {actions.map(([status, label]) => (
              <Button
                key={status + label}
                shape="rounded"
                variant={status === "approved" ? "primary" : "quiet"}
                disabled={move.isPending || (NEEDS_REASON.has(status) && !reason.trim())}
                onClick={() =>
                  move.mutate({ id: a.id, status, reason: reason.trim() }, { onSuccess: () => setReason("") })
                }
              >
                {label}
              </Button>
            ))}
          </FormActions>
        </>
      )}
      <ErrorText error={move.error} className="text-small" />
      {a.status === "approved" && !a.campaign_id && <Workspace aspirant={a} onDone={setLogins} />}
    </Dialog>
  );
}

// A member's own application: what they declared, attached and paid, for vetting.
function Application({ a }) {
  const pay = useMarkNominationFeePaid();
  const [reference, setReference] = useState("");
  return (
    <Card variant="tinted" className="gap-1.5 text-ui" aria-label="Application">
      <div className="text-muted-foreground">Applied in: {a.window_title}</div>
      <div className="text-muted-foreground">Declaration: {a.declared_at ? `signed ${formatDate(a.declared_at)}` : "not yet"}</div>
      <div className="text-muted-foreground">
        Fee: {a.fee_kes ? `${formatKES(a.fee_kes)} · ${a.fee_paid_at ? `paid, ref ${a.fee_reference}` : "not paid"}` : "none"}
      </div>
      <div className="text-muted-foreground">Documents: {a.documents.length === 0 ? "none" : ""}</div>
      {a.documents.map((d) => (
        <a key={d.id} className="font-semibold text-primary underline underline-offset-2" href={`/api/party/nominations/applications/${a.id}/documents/${d.id}/`} target="_blank" rel="noreferrer">{d.label}</a>
      ))}
      {a.fee_kes > 0 && !a.fee_paid_at && a.status === "draft" && (
        <div className="flex flex-wrap gap-2">
          <Input aria-label="Fee reference" className="w-auto flex-[1_1_200px]" placeholder="M-Pesa or bank reference" maxLength={50} value={reference} onChange={(e) => setReference(e.target.value)} />
          <Button shape="rounded" variant="quiet" disabled={pay.isPending || reference.trim().length < 3} onClick={() => pay.mutate({ id: a.id, reference: reference.trim() })}>Mark fee paid</Button>
        </div>
      )}
      <ErrorText error={pay.error} className="text-small" />
    </Card>
  );
}

// The nominations timetable: the officer drafts it, the Super Admin (not the drafter) publishes it.
function Timetable() {
  const windows = useNominationWindows();
  const publish = usePublishNominationWindow();
  const superuser = useAuth((st) => st.user?.is_superuser);
  const [editing, setEditing] = useState(null);
  if (windows.isLoading) return null;
  if (windows.error) return <ErrorText error={windows.error} />;
  return (
    <Card variant="outline" className="gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-card-title font-bold">Nominations timetable</h2>
        <Button shape="rounded" variant="quiet" onClick={() => setEditing({})}>Draft a timetable</Button>
      </div>
      <div className="flex flex-col" aria-label="Timetables">
        {windows.data.length === 0 && <p className="text-ui text-muted-foreground">No timetable yet. Members can apply only inside a published one.</p>}
        {windows.data.map((w) => (
          <div key={w.id} className="flex flex-wrap items-center gap-2 border-t border-line-soft py-2.5 text-ui first:border-0">
            <span className="font-semibold">{w.title}</span>
            <span className="text-muted-foreground">{formatDate(w.opens_on)} – {formatDate(w.closes_on)}</span>
            <span className="text-muted-foreground">{w.seats.map((x) => `${SEAT_LABEL[x.seat]} ${x.fee_kes ? formatKES(x.fee_kes) : "no fee"}`).join(" · ")}</span>
            <Badge tone={w.status === "published" ? "ok" : "warn"}>{w.status === "published" ? "Published" : "Draft"}</Badge>
            {w.status === "draft" && <Button shape="rounded" variant="quiet" size="sm" onClick={() => setEditing(w)}>Edit</Button>}
            {w.status === "draft" && superuser && !w.mine && (
              <Button shape="rounded" size="sm" disabled={publish.isPending} onClick={() => publish.mutate(w.id)}>Publish</Button>
            )}
            {w.status === "draft" && w.mine && (
              <span className="text-muted-foreground">
                {superuser
                  ? "You drafted it, so you cannot publish it. A Nominations Officer opens Edit and saves it, then you publish. Give that office in the console, on a staff login linked to an approved member."
                  : "The Party Super Admin publishes it."}
              </span>
            )}
          </div>
        ))}
      </div>
      <ErrorText error={publish.error} className="text-small" />
      {editing && <TimetableForm window={editing} onClose={() => setEditing(null)} />}
    </Card>
  );
}

function TimetableForm({ window: w, onClose }) {
  const draft = useDraftNominationWindow();
  const revise = useReviseNominationWindow();
  const save = w.id ? revise : draft;
  const fees = Object.fromEntries((w.seats || []).map((x) => [x.seat, String(x.fee_kes)]));
  const [form, setForm] = useState({ title: w.title || "", opens_on: w.opens_on || "", closes_on: w.closes_on || "", requirements: w.requirements || "" });
  const [seats, setSeats] = useState(fees);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const chosen = Object.entries(seats).map(([seat, fee]) => ({ seat, fee_kes: Number(fee) || 0 }));
  const ready = form.title.trim() && form.opens_on && form.closes_on && form.closes_on >= form.opens_on && chosen.length > 0;
  const submit = () => {
    const body = { ...form, seats: chosen };
    save.mutate(w.id ? { id: w.id, body } : body, { onSuccess: onClose });
  };
  return (
    <Dialog title={w.id ? "Edit timetable" : "Draft a timetable"} description="A draft stays private until the Super Admin publishes it." onClose={onClose}>
      <Input aria-label="Title" placeholder="e.g. Nominations 2027" maxLength={150} value={form.title} onChange={set("title")} />
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Opens"><Input aria-label="Opens" type="date" value={form.opens_on} onChange={set("opens_on")} /></Field>
        <Field label="Closes"><Input aria-label="Closes" type="date" value={form.closes_on} onChange={set("closes_on")} /></Field>
      </div>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-small font-semibold">Seats and nomination fees (KES)</legend>
        {SEATS.map(([value, label]) => (
          <div key={value} className="flex flex-wrap items-center gap-3">
            <label className="flex min-h-11 min-w-32 items-center gap-2.5 text-body">
              <input type="checkbox" className="size-[18px] accent-primary" checked={value in seats}
                onChange={(e) => { const next = { ...seats }; if (e.target.checked) next[value] = "0"; else delete next[value]; setSeats(next); }} />
              {label}
            </label>
            {value in seats && (
              <Input aria-label={`${label} fee`} type="number" min={0} className="w-auto flex-[1_1_140px]" value={seats[value]}
                onChange={(e) => setSeats({ ...seats, [value]: e.target.value })} />
            )}
          </div>
        ))}
      </fieldset>
      <Textarea aria-label="Requirements" rows={4} maxLength={5000} placeholder="Requirements aspirants must meet" value={form.requirements} onChange={set("requirements")} />
      <ErrorText error={save.error} className="text-small" />
      <FormActions>
        <Button shape="rounded" variant="quiet" onClick={onClose}>Cancel</Button>
        <Button shape="rounded" disabled={!ready || save.isPending} onClick={submit}>{save.isPending ? "Saving…" : "Save draft"}</Button>
      </FormActions>
    </Dialog>
  );
}

// A record opened from a link (`?open=<id>`), once it has loaded.
function Linked({ id, onClose }) {
  const detail = useAspirant(id);
  return detail.data ? <Detail row={detail.data} onClose={onClose} /> : null;
}

export default function Aspirants() {
  const [status, setStatus] = useState("");
  const [seat, setSeat] = useState("");
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState(null);
  const [nominating, setNominating] = useState(false);
  const [params, setParams] = useSearchParams();
  const linked = params.get("open");
  const closeLinked = () => setParams((p) => { p.delete("open"); return p; }, { replace: true });
  // A link's `?status=` sets the filter each time the link changes.
  const wanted = params.get("status");
  const [applied, setApplied] = useState(null);
  if (wanted !== null && wanted !== applied) {
    setApplied(wanted);
    setStatus(wanted);
    setOffset(0);
  }
  const { data, isLoading, error } = useAspirants({ status, seat, limit: PAGE_SIZE, offset });
  const total = data?.total ?? 0;
  const items = data?.items || [];

  if (isLoading) return <LoadingText />;
  if (error) return <ErrorText error={error} />;

  return (
    <>
      <SlottedHeader
        title="Aspirants"
        sub={`${total} nominations`}
        actions={<Button shape="rounded" onClick={() => setNominating(true)}>Nominate a member</Button>}
      />
      <Timetable />
      <div className="flex flex-wrap gap-2">
        <NativeSelect aria-label="Status" className="w-auto min-w-0 flex-[1_1_180px]" value={status}
          onChange={(e) => { setStatus(e.target.value); setOffset(0); }}>
          <option value="">All statuses</option>
          {Object.entries(ASPIRANT_STATUS_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </NativeSelect>
        <NativeSelect aria-label="Seat filter" className="w-auto min-w-0 flex-[1_1_180px]" value={seat}
          onChange={(e) => { setSeat(e.target.value); setOffset(0); }}>
          <option value="">All seats</option>
          {SEATS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </NativeSelect>
      </div>
      <Card variant="outline">
        <Table stack minWidth={640}>
          <THead><TR><TH>Name</TH><TH>Seat</TH><TH>Area</TH><TH>Status</TH><TH>Workspace</TH></TR></THead>
          <TBody>
            {items.map((a) => (
              <TR key={a.id}>
                <TD><RowButton onClick={() => setOpen(a)}>{a.member.full_name}</RowButton></TD>
                <TD className="text-muted-foreground">{SEAT_LABEL[a.seat]}</TD>
                <TD className="text-muted-foreground">{a.area.name}</TD>
                <TD><Badge tone={ASPIRANT_STATUS_TONE[a.status]}>{ASPIRANT_STATUS_LABEL[a.status]}</Badge></TD>
                <TD className="text-muted-foreground">{a.campaign_id ? "Created" : "—"}</TD>
              </TR>
            ))}
            {items.length === 0 && <TR><TD colSpan={5} className="text-center text-muted-foreground">No nominations match.</TD></TR>}
          </TBody>
        </Table>
      </Card>
      <Pager offset={offset} size={PAGE_SIZE} shown={items.length} total={total} noun="nominations" onChange={setOffset} />
      {nominating && <Nominate onClose={() => setNominating(false)} />}
      {open && <Detail row={open} onClose={() => setOpen(null)} />}
      {linked && !open && <Linked id={linked} onClose={closeLinked} />}
    </>
  );
}
