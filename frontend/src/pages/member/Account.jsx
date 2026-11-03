// /account: a member's card, volunteering, party events, and data & privacy.
import { useState } from "react";
import { Link } from "react-router-dom";
import { useAccount, useChangeVolunteering, useLeaveParty, useParty, usePublicPosts, useStopVolunteering } from "@/api/hooks";
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
  VOLUNTEER_STATUS_LABEL,
} from "../party/helpers";

const MEMBER_STATUS = { approved: ["Active member", "ok"], pending: ["Application pending", "warn"], suspended: ["Suspended", "bad"] };
const monthYear = (iso) => new Date(iso).toLocaleDateString("en-GB", { month: "long", year: "numeric" });
const day = (iso) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
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
      {change.error ? <p role="alert" className="text-small font-semibold text-destructive">{change.error.message}</p> : null}
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
                <span className="text-small text-muted-foreground">{[day(e.event_date), e.venue].filter(Boolean).join(" · ")}</span>
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
          <span className="text-meta text-muted-foreground">Given {day(account.consent_at)}</span>
        </div>
        {account.volunteer ? (
          <div className="flex flex-col gap-1">
            <span className="font-bold">Volunteer contact</span>
            <span className="text-small text-muted-foreground">{account.volunteer.consent_wording}</span>
            <span className="text-meta text-muted-foreground">Given {day(account.volunteer.consent_at)}</span>
          </div>
        ) : null}
        {stop.error || leave.error ? <p role="alert" className="text-small font-semibold text-destructive">{(stop.error || leave.error).message}</p> : null}
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

export default function Account() {
  const account = useAccount();
  const party = useParty().data;
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
          <TabsTrigger value="data">My data &amp; privacy</TabsTrigger>
        </TabsList>
        <TabsContent value="volunteering"><Volunteering account={a} wording={party?.volunteer_consent_wording} /></TabsContent>
        <TabsContent value="events"><PartyEvents /></TabsContent>
        <TabsContent value="data"><DataAndPrivacy account={a} party={party} /></TabsContent>
      </Tabs>
    </div>
  );
}
