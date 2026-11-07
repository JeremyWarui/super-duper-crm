// /candidates/:slug: one candidate's profile, the party events naming them, and the "Support" dialog.
// CandidateView is the page body, which an aspirant installation's homepage shows as well.
import { useState } from "react";
import { Link } from "react-router-dom";
import { useCandidateVolunteer, usePartyPlaces, usePublicCandidate } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input, NativeSelect } from "@/components/ui/input";
import { Crumbs } from "@/components/ui/typography";
import { AREAS, CONTACT_METHODS, PROFESSIONS, SEATS } from "@/pages/party/helpers";
import { Photo, day } from "./story";

export const SEAT_TITLE = { mca: "Member of County Assembly", mp: "Member of Parliament", governor: "Governor", senator: "Senator", women_rep: "Women Representative" };
const SEAT_NAME = Object.fromEntries(SEATS.map(([value, label]) => [value, label]));
const TABS = ["About", "Priorities", "Events"];
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const PILL = "flex min-h-11 cursor-pointer items-center gap-2 rounded-full border-[1.5px] border-line-control bg-white px-3.5 text-small font-semibold has-[:checked]:border-primary has-[:checked]:bg-primary-tint";

export const VOLUNTEER_NOTE = "Your details go to the campaign only.";

/** The volunteer box's title: who it is for, or thanks once sent. */
export const volunteerTitle = (c, sent) => (sent ? "Thank you" : `Volunteer for ${c.name.split(/\s+/)[0]}`);

/** The volunteer form, the same in the dialog and on the /volunteer page. */
export function SupportForm({ c, send, withdrawPath }) {
  const [f, setF] = useState({ first_name: "", last_name: "", email: "", phone: "", ward: "", registration_centre: "", profession: "", profession_other: "", areas: [], area_other: "", preferred_contact: "", consent_given: false });
  const centres = usePartyPlaces({ ward: f.ward, enabled: !!f.ward }).data || [];
  const set = (key) => (e) => setF({ ...f, [key]: e.target.value });
  const toggle = (v) => setF({ ...f, areas: f.areas.includes(v) ? f.areas.filter((a) => a !== v) : [...f.areas, v] });
  const ok =
    f.first_name.trim() && f.last_name.trim() && EMAIL.test(f.email.trim()) && f.phone.trim() && f.ward && f.registration_centre &&
    f.profession && (f.profession !== "other" || f.profession_other.trim()) && f.areas.length && (!f.areas.includes("other") || f.area_other.trim()) &&
    f.preferred_contact && f.consent_given;
  const submit = (e) => {
    e.preventDefault();
    if (!ok) return;
    send.mutate({ ...f, first_name: f.first_name.trim(), last_name: f.last_name.trim(), email: f.email.trim(), phone: f.phone.trim(), profession_other: f.profession_other.trim(), area_other: f.area_other.trim() });
  };
  if (send.isSuccess) {
    const link = `${window.location.origin}${withdrawPath}${send.data.withdraw_code}`;
    const thanks = (
      <>
        <p role="status" className="text-text-2">{send.data.message}</p>
        <p className="text-small text-muted-foreground">Keep this link: it takes your details off the campaign's list. <a href={link} className="break-all font-semibold">{link}</a></p>
      </>
    );
    return <div className="flex flex-col gap-3">{thanks}</div>;
  }
  const form = (
      <form onSubmit={submit} noValidate className="flex flex-col gap-3.5">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="First name"><Input value={f.first_name} onChange={set("first_name")} autoComplete="given-name" /></Field>
          <Field label="Last name"><Input value={f.last_name} onChange={set("last_name")} autoComplete="family-name" /></Field>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Field label="Email"><Input type="email" value={f.email} onChange={set("email")} autoComplete="email" /></Field>
          <Field label="Phone"><Input value={f.phone} onChange={set("phone")} inputMode="tel" autoComplete="tel" placeholder="07XX XXX XXX" /></Field>
          <Field label="Preferred contact">
          <NativeSelect value={f.preferred_contact} onChange={set("preferred_contact")}>
            <option value="">Pick a contact method</option>
            {CONTACT_METHODS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </NativeSelect>
        </Field>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="Ward">
          <NativeSelect value={f.ward} onChange={(e) => setF({ ...f, ward: e.target.value, registration_centre: "" })}>
            <option value="">Pick your ward</option>
            {c.wards.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </NativeSelect>
        </Field>
          <Field label="Polling station">
          <NativeSelect value={f.registration_centre} onChange={set("registration_centre")} disabled={!f.ward}>
            <option value="">Pick your polling station</option>
            {centres.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </NativeSelect>
        </Field>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="Profession">
          <NativeSelect value={f.profession} onChange={set("profession")}>
            <option value="">Pick your profession</option>
            {PROFESSIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </NativeSelect>
        </Field>
          {f.profession === "other" ? <Field label="Your profession"><Input value={f.profession_other} maxLength={100} onChange={set("profession_other")} /></Field> : null}
        </div>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-small font-semibold">How would you like to help?</legend>
          <div className="flex flex-wrap gap-2">
            {AREAS.map(([v, l]) => (
              <label key={v} className={PILL}><input type="checkbox" className="size-4 accent-primary" checked={f.areas.includes(v)} onChange={() => toggle(v)} />{l}</label>
            ))}
          </div>
        </fieldset>
        {f.areas.includes("other") ? <Field label="Other ways to help"><Input value={f.area_other} maxLength={100} onChange={set("area_other")} /></Field> : null}
        <label className="flex items-start gap-2.5 text-small leading-[1.5] text-muted-foreground">
          <input type="checkbox" className="mt-0.5 size-[18px] flex-none accent-primary" checked={f.consent_given} onChange={(e) => setF({ ...f, consent_given: e.target.checked })} />
          {c.consent_wording}
        </label>
        {send.error ? <p role="alert" className="text-small font-semibold text-destructive">{send.error.message}</p> : null}
        {!ok ? <p className="text-small text-muted-foreground">Fill in every field, tick at least one way to help and agree above to send this.</p> : null}
        <Button type="submit" disabled={!ok || send.isPending}>{send.isPending ? "Sending…" : "I'll volunteer"}</Button>
      </form>
  );
  return form;
}

/** The candidate's hero band: photo, seat, name, place and slogan, with `actions` below. */
export function CandidateHero({ c, crumbs, actions }) {
  const where = [c.area, c.county].filter((v, i, all) => v && all.indexOf(v) === i).join(", ");
  return (
    <section className="bg-primary text-white">
      <div className="site-container flex flex-col gap-6 pt-10 pb-12">
        {crumbs ? <Crumbs onDark items={crumbs} /> : null}
        <div className="flex flex-wrap items-center gap-9">
          <Photo url={c.photo_url} className="h-[260px] w-[220px] flex-none rounded-band bg-[#0F7049]" />
          <div className="flex min-w-0 flex-[1_1_400px] flex-col gap-3.5">
            <span className="self-start rounded-full bg-accent px-3 py-1.5 text-small font-extrabold uppercase tracking-[0.08em] text-ink">{SEAT_TITLE[c.seat]}</span>
            <h1 className="font-display text-[clamp(40px,5vw,64px)] leading-none font-extrabold tracking-[-0.03em]">{c.name}</h1>
            <p className="text-[19px] text-[#CFE0D5]">{where}{c.slogan ? ` · "${c.slogan}"` : ""}</p>
            <div className="flex flex-wrap gap-3 pt-1">{actions}</div>
          </div>
        </div>
      </div>
    </section>
  );
}

/** The volunteer form in a wide dialog. */
export function VolunteerDialog({ c, send, withdrawPath, onClose }) {
  return (
    <Dialog
      title={volunteerTitle(c, send.isSuccess)}
      description={send.isSuccess ? null : VOLUNTEER_NOTE}
      onClose={onClose}
      className="w-[min(760px,calc(100vw-32px))]"
    >
      <SupportForm c={c} send={send} withdrawPath={withdrawPath} />
    </Dialog>
  );
}

/** A short "Support {first}" card whose button opens the volunteer dialog. */
export function SupportCard({ c, onOpen }) {
  const first = c.name.split(/\s+/)[0];
  return (
    <Card className="gap-3 p-6">
      <h2 className="text-[20px] font-bold">Support {first}</h2>
      <p className="text-text-2">Give a few hours at events, door to door or online. The campaign team will contact you.</p>
      <Button onClick={onOpen}>Volunteer for {first}</Button>
    </Card>
  );
}

export default function Candidate({ slug }) {
  const query = usePublicCandidate(slug);
  const send = useCandidateVolunteer(slug);
  if (query.isLoading) return <div className="site-container py-12 text-muted-foreground">Loading…</div>;
  if (query.error) return <div role="alert" className="site-container py-12">{query.error.message}</div>;
  const c = query.data;
  return (
    <CandidateView
      c={c}
      send={send}
      withdrawPath="/candidates/volunteer/withdraw/"
      crumbs={[{ label: "Home", to: "/" }, { label: "Candidates", to: "/candidates" }, { label: c.area }]}
      note={`Profile written from what the candidate sent, and published by the party. ${SEAT_NAME[c.seat]} aspirant.`}
      events
    />
  );
}

/**
 * One candidate's page: hero, tabs (About, Priorities, and Events where `events`), the volunteer
 * form and the campaign office. `crumbs` and `note` are left out on a homepage.
 */
export function CandidateView({ c, send, withdrawPath, crumbs, note, events = false }) {
  const [tab, setTab] = useState("About");
  const [volunteering, setVolunteering] = useState(false);
  const tabs = events ? TABS : TABS.filter((t) => t !== "Events");
  const first = c.name.split(/\s+/)[0];
  const contact = [c.office_phone, c.office_email].filter(Boolean).join(" · ");
  return (
    <>
      <CandidateHero
        c={c}
        crumbs={crumbs}
        actions={
          <>
            {c.volunteering_open ? <Button variant="accent" onClick={() => setVolunteering(true)}>Volunteer for this campaign</Button> : null}
            {events && c.events.length ? <Button asChild variant="onDark"><a href="#events" onClick={() => setTab("Events")}>Meet the candidate</a></Button> : null}
          </>
        }
      />
      <div className="border-b border-line-2 bg-white">
        <div role="tablist" aria-label="Profile sections" className="site-container flex flex-wrap gap-1">
          {tabs.map((t) => (
            <button key={t} type="button" role="tab" aria-selected={tab === t} onClick={() => setTab(t)} className={`min-h-12 cursor-pointer px-4 text-[15px] font-bold ${tab === t ? "text-primary shadow-[inset_0_-3px_0_var(--party-primary)]" : "text-ink"}`}>{t}</button>
          ))}
        </div>
      </div>
      <div className="site-container flex flex-wrap items-start gap-10 pt-12 pb-20">
        <div role="tabpanel" aria-label={tab} className="flex min-w-0 flex-[999_1_560px] flex-col gap-4">
          {tab === "About" ? (
            <>
              <h2 className="rule-top font-display text-[32px] font-extrabold">About {first}</h2>
              {c.bio ? c.bio.split(/\n+/).filter(Boolean).map((p, n) => <p key={n} className="text-[18px] leading-[1.7] text-text-2">{p}</p>) : <p className="text-muted-foreground">The campaign has not sent a biography yet.</p>}
            </>
          ) : null}
          {tab === "Priorities" ? (
            <>
              <h2 className="rule-top font-display text-[32px] font-extrabold">Priorities for {c.area}</h2>
              {c.priorities.length ? c.priorities.map((p, n) => (
                <Card key={n} className="flex-row gap-4 p-5">
                  <span className="font-display text-[22px] font-extrabold text-primary">{n + 1}</span>
                  <span className="flex flex-col gap-1"><strong className="text-[18px]">{p.title}</strong>{p.text ? <span className="text-muted-foreground">{p.text}</span> : null}</span>
                </Card>
              )) : <p className="text-muted-foreground">No priorities published yet.</p>}
            </>
          ) : null}
          {tab === "Events" ? (
            <section id="events" className="flex flex-col gap-3.5">
              <h2 className="rule-top font-display text-[32px] font-extrabold">Meet {first}</h2>
              {c.events.length ? c.events.map((e) => (
                <Card key={e.id} asChild interactive className="flex-row flex-wrap items-center justify-between gap-3 p-[18px]">
                  <Link to={`/news/${e.id}`}>
                    <span className="flex flex-col gap-1"><strong className="text-[17px]">{e.title}</strong><span className="text-small text-muted-foreground">{[day(e.event_date, { weekday: "short", day: "numeric", month: "long" }), e.venue].filter(Boolean).join(" · ")}</span></span>
                    <span className="font-bold text-primary">Details →</span>
                  </Link>
                </Card>
              )) : <p className="text-muted-foreground">No party events are planned with {first} yet.</p>}
            </section>
          ) : null}
        </div>
        <aside id="support" className="flex min-w-0 flex-[1_1_320px] flex-col gap-5">
          {c.volunteering_open ? <SupportCard c={c} onOpen={() => setVolunteering(true)} /> : null}
          {c.office_address || contact ? (
            <Card variant="ink" className="gap-2 text-[15px]">
              <h2 className="mb-1 text-[18px] font-bold">Campaign office</h2>
              {c.office_address ? <span className="text-on-dark-muted">{c.office_address}</span> : null}
              {contact ? <span className="text-on-dark-muted">{contact}</span> : null}
            </Card>
          ) : null}
          {note ? <p className="text-small text-muted-foreground">{note}</p> : null}
        </aside>
      </div>
      {volunteering ? <VolunteerDialog c={c} send={send} withdrawPath={withdrawPath} onClose={() => setVolunteering(false)} /> : null}
    </>
  );
}
