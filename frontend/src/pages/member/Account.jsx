// /account: a member's card, volunteering, party events, and data & privacy.
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  useAccount, useApplyToVie, useAttachNominationDocument, useChangeVolunteering, useDetachNominationDocument, useLeaveParty,
  useMyNomination, useSite, usePublicPosts, useStopVolunteering, useSubmitNomination, useWithdrawNomination,
} from "@/api/hooks";
import PayDialog from "@/components/PayDialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, NativeSelect } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/store/auth";
import {
  AREAS,
  AREA_LABEL,
  CONTACT_LABEL,
  CONTACT_METHODS,
  PROFESSIONS,
  PROFESSION_LABEL,
  SEAT_LABEL,
  VOLUNTEER_STATUS_LABEL,
} from "../party/helpers";
import { formatDate, formatKES } from "../../lib/format";
import { ErrorText } from "@/components/ui/error-text";

const MEMBER_STATUS = { approved: ["Active member", "ok"], pending: ["Application pending", "warn"], suspended: ["Suspended", "bad"] };
const monthYear = (iso) => new Date(iso).toLocaleDateString("en-GB", { month: "long", year: "numeric" });
const place = (a) => [a.ward?.name, a.county?.name].filter(Boolean).join(", ");

function MemberCard({ account }) {
  const [label, tone] = MEMBER_STATUS[account.status] || [account.status, "stone"];
  return (
    <div className="flex flex-wrap gap-5">
      <section aria-label="Member card" className="flex min-w-0 flex-[1_1_380px] flex-col gap-5 rounded-panel bg-primary p-7 text-white">
        <div className="flex flex-col gap-1">
          <span className="text-meta font-extrabold tracking-[0.12em] text-accent">MEMBER CARD</span>
          <span className="font-display text-[28px] font-extrabold">{account.full_name}</span>
        </div>
        <dl className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-4 text-small">
          <div className="flex flex-col gap-0.5"><dt className="text-[#CFE0D5]">Branch</dt><dd className="font-bold">{place(account)}</dd></div>
          <div className="flex flex-col gap-0.5"><dt className="text-[#CFE0D5]">Polling station</dt><dd className="font-bold">{account.registration_centre?.name || "Not set"}</dd></div>
          <div className="flex flex-col gap-0.5"><dt className="text-[#CFE0D5]">Member since</dt><dd className="font-bold">{monthYear(account.member_since)}</dd></div>
        </dl>
        <span className="text-small text-[#CFE0D5]">Show this card at branch meetings and party events.</span>
      </section>
      <Card className="flex-[1_1_300px]">
        <h2 className="font-display text-card-title font-extrabold">Membership status</h2>
        <Badge tone={tone} className="self-start">{label}</Badge>
        <p className="text-body text-muted-foreground">Your membership is free. The party office can correct your name, phone, ward or polling station.</p>
      </Card>
    </div>
  );
}

const blank = { profession: "", profession_other: "", areas: [], area_other: "", preferred_contact: "", consent_given: false };

/** The volunteer fields, for a first sign-up or a change. */
function VolunteerForm({ volunteer, wording, onDone, onCancel }) {
  const change = useChangeVolunteering();
  const [form, setForm] = useState(() =>
    volunteer
      ? { ...blank, ...volunteer, profession: volunteer.profession || "", consent_given: true }
      : blank,
  );
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));
  const toggle = (value) =>
    set({ areas: form.areas.includes(value) ? form.areas.filter((a) => a !== value) : [...form.areas, value] });
  const submit = (e) => {
    e.preventDefault();
    const { profession, profession_other, areas, area_other, preferred_contact, consent_given } = form;
    change.mutate({ profession, profession_other, areas, area_other, preferred_contact, consent_given }, { onSuccess: onDone });
  };
  return (
    <form onSubmit={submit} className="flex max-w-[620px] flex-col gap-4">
      <Field label="Profession">
        <NativeSelect required value={form.profession} onChange={(e) => set({ profession: e.target.value })}>
          <option value="">Pick your profession</option>
          {PROFESSIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </NativeSelect>
      </Field>
      {form.profession === "other" ? (
        <Field label="Your profession"><Input required maxLength={100} value={form.profession_other} onChange={(e) => set({ profession_other: e.target.value })} /></Field>
      ) : null}
      <fieldset className="flex flex-col gap-2">
        <legend className="pb-1 text-small font-semibold">How would you like to help?</legend>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-x-4 gap-y-1">
          {AREAS.map(([value, label]) => (
            <label key={value} className="flex min-h-11 items-center gap-2.5 text-body">
              <input type="checkbox" className="size-[18px] accent-primary" checked={form.areas.includes(value)} onChange={() => toggle(value)} />
              {label}
            </label>
          ))}
        </div>
      </fieldset>
      {form.areas.includes("other") ? (
        <Field label="Other ways to help"><Input required maxLength={100} value={form.area_other} onChange={(e) => set({ area_other: e.target.value })} /></Field>
      ) : null}
      <Field label="Preferred contact">
        <NativeSelect required value={form.preferred_contact} onChange={(e) => set({ preferred_contact: e.target.value })}>
          <option value="">Pick a contact method</option>
          {CONTACT_METHODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </NativeSelect>
      </Field>
      <label className="flex items-start gap-2.5 text-body">
        <input type="checkbox" required className="mt-1 size-[18px] accent-primary" checked={form.consent_given} onChange={(e) => set({ consent_given: e.target.checked })} />
        {wording}
      </label>
      <ErrorText error={change.error} className="text-small" />
      <div className="flex flex-wrap gap-2.5">
        <Button type="submit" disabled={change.isPending || form.areas.length === 0}>{volunteer ? "Save my volunteer details" : "Volunteer for events"}</Button>
        {onCancel ? <Button type="button" variant="quiet" onClick={onCancel}>Cancel</Button> : null}
      </div>
    </form>
  );
}

function Volunteering({ account, wording }) {
  const [editing, setEditing] = useState(false);
  const v = account.volunteer;
  if (!v) {
    return (
      <Card>
        <h2 className="font-display text-card-title font-extrabold">Volunteer for events</h2>
        <p className="text-body text-muted-foreground">Help your branch at events, door to door and online. Tell us how you would like to help.</p>
        <VolunteerForm wording={wording} onDone={() => {}} />
      </Card>
    );
  }
  const areas = v.areas.map((a) => (a === "other" ? v.area_other : AREA_LABEL[a])).filter(Boolean);
  return (
    <div className="flex flex-wrap gap-5">
      <Card className="flex-[3_1_520px]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-display text-card-title font-extrabold">My volunteering</h2>
          <Badge tone={v.status === "active" ? "ok" : v.status === "interested" ? "warn" : "stone"}>{VOLUNTEER_STATUS_LABEL[v.status]}</Badge>
        </div>
        {editing ? (
          <VolunteerForm volunteer={v} wording={wording} onDone={() => setEditing(false)} onCancel={() => setEditing(false)} />
        ) : (
          <>
            <dl className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4 text-body">
              <div><dt className="text-small text-muted-foreground">Ways to help</dt><dd className="font-semibold">{areas.join(", ")}</dd></div>
              <div><dt className="text-small text-muted-foreground">Profession</dt><dd className="font-semibold">{v.profession === "other" ? v.profession_other : PROFESSION_LABEL[v.profession]}</dd></div>
              <div><dt className="text-small text-muted-foreground">Preferred contact</dt><dd className="font-semibold">{CONTACT_LABEL[v.preferred_contact]}</dd></div>
            </dl>
            <Button variant="outline" className="self-start" onClick={() => setEditing(true)}>Change my volunteer details</Button>
          </>
        )}
      </Card>
      <Card className="flex-[2_1_320px]">
        <h2 className="font-display text-card-title font-extrabold">My volunteer tasks</h2>
        <p className="text-body text-muted-foreground">No tasks yet. Your branch will contact you when there is something to do.</p>
        <p className="text-small text-muted-foreground">
          Volunteering for a candidate's campaign happens on their <Link to="/candidates">profile page</Link>.
        </p>
      </Card>
    </div>
  );
}

function PartyEvents() {
  const events = usePublicPosts("event");
  if (events.isLoading) return <p className="text-muted-foreground">Loading…</p>;
  const list = events.data || [];
  return (
    <Card>
      <h2 className="font-display text-card-title font-extrabold">Party events</h2>
      {list.length ? (
        <ul className="flex flex-col divide-y divide-line">
          {list.map((e) => (
            <li key={e.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <span className="flex flex-col">
                <Link to={`/news/${e.id}`} className="font-bold">{e.title}</Link>
                <span className="text-small text-muted-foreground">{[formatDate(e.event_date), e.venue].filter(Boolean).join(" · ")}</span>
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-body text-muted-foreground">No party events are coming up.</p>
      )}
    </Card>
  );
}

function DataAndPrivacy({ account, party }) {
  const stop = useStopVolunteering();
  const leave = useLeaveParty();
  const logout = useAuth((s) => s.logout);
  const [leaving, setLeaving] = useState(false);
  const office = [party?.contact_email, party?.contact_phone].filter(Boolean).join(" or ");
  return (
    <div className="flex flex-wrap gap-5">
      <Card className="flex-[1_1_360px]">
        <h2 className="font-display text-card-title font-extrabold">My details</h2>
        <dl className="grid grid-cols-[120px_1fr] gap-x-4 gap-y-2.5 text-body">
          <dt className="text-muted-foreground">Name</dt><dd>{account.full_name}</dd>
          <dt className="text-muted-foreground">Phone</dt><dd>{account.phone}</dd>
          <dt className="text-muted-foreground">Email</dt><dd>{account.email || "None"}</dd>
          <dt className="text-muted-foreground">Branch</dt><dd>{place(account)}</dd>
          <dt className="text-muted-foreground">Polling station</dt><dd>{account.registration_centre?.name || "Not set"}</dd>
        </dl>
        <p className="text-small text-muted-foreground">To correct your name, phone, ward or polling station, contact the party office{office ? ` at ${office}` : ""}.</p>
      </Card>
      <Card className="flex-[1_1_360px]">
        <h2 className="font-display text-card-title font-extrabold">My consents</h2>
        <div className="flex flex-col gap-1">
          <span className="font-bold">Membership</span>
          <span className="text-small text-muted-foreground">{account.consent_wording}</span>
          <span className="text-meta text-muted-foreground">Given {formatDate(account.consent_at)}</span>
        </div>
        {account.volunteer ? (
          <div className="flex flex-col gap-1">
            <span className="font-bold">Volunteer contact</span>
            <span className="text-small text-muted-foreground">{account.volunteer.consent_wording}</span>
            <span className="text-meta text-muted-foreground">Given {formatDate(account.volunteer.consent_at)}</span>
          </div>
        ) : null}
        <ErrorText error={stop.error || leave.error} className="text-small" />
        <div className="flex flex-wrap gap-2.5 pt-1">
          {account.volunteer ? (
            <Button variant="outline" disabled={stop.isPending} onClick={() => stop.mutate()}>Stop volunteering</Button>
          ) : null}
          {leaving ? (
            <span className="flex flex-wrap items-center gap-2.5">
              <span className="text-small font-semibold">Leave {party?.name || "the party"}? This signs you out.</span>
              <Button variant="danger" disabled={leave.isPending} onClick={() => leave.mutate(undefined, { onSuccess: logout })}>Yes, leave the party</Button>
              <Button variant="quiet" onClick={() => setLeaving(false)}>Keep my membership</Button>
            </span>
          ) : (
            <Button variant="danger" onClick={() => setLeaving(true)}>Leave the party</Button>
          )}
        </div>
        <Link to="/privacy" className="text-small font-semibold">Read the privacy notice</Link>
      </Card>
    </div>
  );
}

const ASPIRANT_STATUS = { draft: ["Not submitted", "warn"], submitted: ["With the vetting team", "info"], approved: ["Approved aspirant", "ok"], suspended: ["Suspended", "bad"] };

// Applying to vie: pick a seat open in the window, attach documents, have the fee marked paid,
// then declare and submit. The nominations office vets it.
function MyNomination() {
  const mine = useMyNomination();
  if (mine.isLoading) return <p className="text-muted-foreground">Loading…</p>;
  if (mine.error) return <p role="alert">{mine.error.message}</p>;
  const { window: notice, choices, application } = mine.data;
  if (application) return <Application application={application} notice={notice} />;
  if (choices.length) return <Choose notice={notice} choices={choices} />;
  return (
    <Card className="gap-2 p-6">
      <h2 className="font-display text-card-title font-extrabold">Vie for a seat</h2>
      <p className="text-muted-foreground">
        {notice && !notice.open ? `Applications for ${notice.title} open on ${formatDate(notice.opens_on)}.` : "No nominations are open now. The timetable is published on the Vie with us page."}
      </p>
    </Card>
  );
}

function Choose({ notice, choices }) {
  const apply = useApplyToVie();
  const [seat, setSeat] = useState(choices[0].seat);
  return (
    <Card className="gap-4 p-6" role="region" aria-label="Apply for nomination">
      <div>
        <h2 className="font-display text-card-title font-extrabold">Apply for nomination</h2>
        <p className="text-muted-foreground">{notice.title} · applications close {formatDate(notice.closes_on)}</p>
      </div>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 font-semibold">Which seat are you vying for?</legend>
        {choices.map((c) => (
          <label key={c.seat} className={`flex min-h-12 cursor-pointer items-center gap-3 rounded-lg border px-4 py-2 ${seat === c.seat ? "border-primary bg-primary-tint" : "border-line"}`}>
            <input type="radio" name="seat" value={c.seat} checked={seat === c.seat} onChange={() => setSeat(c.seat)} />
            <span className="flex-1"><strong>{SEAT_LABEL[c.seat]}</strong> <span className="text-muted-foreground">· {c.area}</span></span>
            <span className="text-small tabular-nums">{c.fee_kes ? formatKES(c.fee_kes) : "No fee"}</span>
          </label>
        ))}
      </fieldset>
      <p className="text-small text-muted-foreground">You vie in your own registered area.</p>
      <ErrorText error={apply.error} />
      <Button className="self-start" disabled={apply.isPending} onClick={() => apply.mutate(seat)}>{apply.isPending ? "Starting…" : "Start application"}</Button>
    </Card>
  );
}

function Application({ application: a, notice }) {
  const attach = useAttachNominationDocument();
  const detach = useDetachNominationDocument();
  const submit = useSubmitNomination();
  const withdraw = useWithdrawNomination();
  const [label, setLabel] = useState("");
  const [file, setFile] = useState(null);
  const [declared, setDeclared] = useState(false);
  const [paying, setPaying] = useState(false);
  const [statusLabel, tone] = ASPIRANT_STATUS[a.status] || [a.status, "stone"];
  const draft = a.status === "draft" && a.from_window;
  const failed = attach.error || detach.error || submit.error || withdraw.error;
  const feeDue = a.fee_kes > 0 && !a.fee_paid;
  return (
    <Card className="gap-5 p-6" role="region" aria-label="My nomination">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="font-display text-card-title font-extrabold">{SEAT_LABEL[a.seat]} · {a.area}</h2>
        <Badge tone={tone}>{statusLabel}</Badge>
      </div>
      <ErrorText error={failed} />
      {a.status === "submitted" && <p>Submitted. The nominations office vets your application and will contact you.</p>}
      {a.status === "approved" && <p>You are an approved aspirant. The party office will set up your campaign workspace.</p>}
      {(a.documents.length > 0 || draft) && (
        <div className="flex flex-col gap-2">
          <h3 className="font-bold">Documents</h3>
          {a.documents.length === 0 && <p className="text-muted-foreground">None yet. Add your ID, voter's card and anything the requirements ask for.</p>}
          <ul className="flex flex-col gap-1">
            {a.documents.map((d) => (
              <li key={d.id} className="flex items-center justify-between gap-3 border-b border-line py-2">
                <span>{d.label}</span>
                {draft && <Button size="sm" variant="quiet" disabled={detach.isPending} onClick={() => detach.mutate(d.id)} aria-label={`Remove ${d.label}`}>Remove</Button>}
              </li>
            ))}
          </ul>
          {draft && (
            <div className="flex flex-wrap items-end gap-3">
              <Field label="Document" className="min-w-0 flex-[1_1_200px]"><Input value={label} maxLength={100} placeholder="e.g. National ID" onChange={(e) => setLabel(e.target.value)} /></Field>
              <Field label="File (PDF or photo)" className="min-w-0 flex-[1_1_200px]"><input type="file" accept="application/pdf,image/*" onChange={(e) => setFile(e.target.files?.[0] || null)} /></Field>
              <Button variant="quiet" disabled={!label.trim() || !file || attach.isPending} onClick={() => attach.mutate({ file, label: label.trim() }, { onSuccess: () => { setLabel(""); setFile(null); } })}>{attach.isPending ? "Uploading…" : "Add document"}</Button>
            </div>
          )}
        </div>
      )}
      {a.fee_kes > 0 && (
        <div className="flex flex-col gap-1">
          <h3 className="font-bold">Nomination fee</h3>
          <p>
            {formatKES(a.fee_kes)} ·{" "}
            {a.fee_paid ? "Paid" : a.fee_waiting ? "Your M-Pesa code is with the nominations office to confirm." : "Not paid yet."}
          </p>
          {draft && feeDue && !a.fee_waiting ? <Button className="self-start" onClick={() => setPaying(true)}>Pay with M-Pesa</Button> : null}
          {paying ? <PayDialog title="Pay the nomination fee" fee={a.fee_kes} onClose={() => setPaying(false)} /> : null}
        </div>
      )}
      {draft && (
        <>
          <label className="flex items-start gap-3">
            <input type="checkbox" className="mt-1" checked={declared} onChange={(e) => setDeclared(e.target.checked)} />
            <span>I confirm the information and documents are true, I meet the requirements for this seat, and I will abide by the party's nomination rules and the outcome of the process.</span>
          </label>
          <div className="flex flex-wrap gap-2">
            <Button disabled={!declared || feeDue || submit.isPending} onClick={() => submit.mutate()}>{submit.isPending ? "Submitting…" : "Submit application"}</Button>
            <Button variant="quiet" disabled={withdraw.isPending} onClick={() => withdraw.mutate()}>Withdraw</Button>
          </div>
          {feeDue && <p className="text-small text-muted-foreground">You can submit once the fee is paid.</p>}
        </>
      )}
      {a.status === "submitted" && a.from_window && <Button variant="quiet" className="self-start" disabled={withdraw.isPending} onClick={() => withdraw.mutate()}>Withdraw application</Button>}
      {notice && draft && <p className="text-small text-muted-foreground">Applications close {formatDate(notice.closes_on)}.</p>}
    </Card>
  );
}

export default function Account() {
  const account = useAccount();
  const party = useSite().data;
  if (account.isLoading) return <div className="site-container py-10 text-muted-foreground">Loading…</div>;
  if (account.error) return <div role="alert" className="site-container py-10">{account.error.message}</div>;
  const a = account.data;
  return (
    <div className="site-container flex flex-col gap-7 pt-10 pb-20">
      <h1 className="font-display text-section font-extrabold tracking-[-0.02em]">Habari, {a.first_name}</h1>
      <MemberCard account={a} />
      <Tabs look="underline" defaultValue="volunteering" className="gap-6">
        <TabsList aria-label="Account sections" className="flex-nowrap overflow-x-auto border-b border-line whitespace-nowrap">
          <TabsTrigger value="volunteering">Volunteering</TabsTrigger>
          <TabsTrigger value="events">Party events</TabsTrigger>
          <TabsTrigger value="nomination">My nomination</TabsTrigger>
          <TabsTrigger value="data">My data &amp; privacy</TabsTrigger>
        </TabsList>
        <TabsContent value="volunteering"><Volunteering account={a} wording={party?.volunteer_consent_wording} /></TabsContent>
        <TabsContent value="events"><PartyEvents /></TabsContent>
        <TabsContent value="nomination"><MyNomination /></TabsContent>
        <TabsContent value="data"><DataAndPrivacy account={a} party={party} /></TabsContent>
      </Tabs>
    </div>
  );
}
