// /candidates/:slug: one candidate's profile, the party events naming them, and the "Support" dialog.
// CandidateView is the page body, which an aspirant installation's homepage shows as well.
import { useState } from "react";
import { Link } from "react-router-dom";
import { useCandidateVolunteer, usePartyPlaces, usePublicCandidate } from "@/api/hooks";
import { RichText } from "@/components/RichTextView";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Check, Field, FilterSelect, Input } from "@/components/ui/input";
import { Crumbs, RuleHead } from "@/components/ui/typography";
import { SEAT_LABEL } from "@/lib/labels";
import VolunteerFields, { NO_VOLUNTEER, volunteerBody, volunteerReady } from "@/components/VolunteerFields";
import { firstName, formatDay, linkTo, whereOf } from "@/lib/format";
import { Photo } from "./story";
import { isEmail } from "@/lib/email";
import { ErrorText } from "@/components/ui/error-text";
import { pageState } from "@/components/PageState";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useForm } from "@/lib/form";

/** The seat an aspirant is vying for, as their badge says it. */
export const vying = (seat) => `Vying for ${SEAT_LABEL[seat]}`;
const TABS = ["About", "Priorities", "Events"];

export const VOLUNTEER_NOTE = "Your details go to the campaign only.";

/** The volunteer box's title: who it is for, or thanks once sent. */
export const volunteerTitle = (c, sent) => (sent ? "Thank you" : `Volunteer for ${firstName(c.name)}`);

/** The volunteer form, the same in the dialog and on the /volunteer page. */
export function SupportForm({ c, send, withdrawPath }) {
  const [f, setF, set] = useForm({ first_name: "", last_name: "", email: "", phone: "", ward: "", registration_centre: "", ...NO_VOLUNTEER, consent_given: false });
  const centres = usePartyPlaces({ ward: f.ward, enabled: !!f.ward }).data || [];
  const ok =
    f.first_name.trim() && f.last_name.trim() && isEmail(f.email) && f.phone.trim() && f.ward && f.registration_centre &&
    volunteerReady(f) && f.consent_given;
  const submit = (e) => {
    e.preventDefault();
    if (!ok) return;
    send.mutate({ ...f, first_name: f.first_name.trim(), last_name: f.last_name.trim(), email: f.email.trim(), phone: f.phone.trim(), ...volunteerBody(f) });
  };
  if (send.isSuccess) {
    const link = linkTo(`${withdrawPath}${send.data.withdraw_code}`);
    return (
      <div className="flex flex-col gap-3">
        <p role="status" className="text-text-2">{send.data.message}</p>
        <p className="text-small text-muted-foreground">Keep this link: it takes your details off the campaign's list. <a href={link} className="break-all font-semibold">{link}</a></p>
      </div>
    );
  }
  return (
      <form onSubmit={submit} noValidate className="flex flex-col gap-3.5">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="First name"><Input value={f.first_name} onChange={set("first_name")} autoComplete="given-name" /></Field>
          <Field label="Last name"><Input value={f.last_name} onChange={set("last_name")} autoComplete="family-name" /></Field>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="Email"><Input type="email" value={f.email} onChange={set("email")} autoComplete="email" /></Field>
          <Field label="Phone"><Input value={f.phone} onChange={set("phone")} inputMode="tel" autoComplete="tel" placeholder="07XX XXX XXX" /></Field>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <FilterSelect labelled label="Ward" blank="Pick your ward" value={f.ward} options={c.wards} onChange={(ward) => setF({ ...f, ward, registration_centre: "" })} />
          <FilterSelect labelled label="Polling station" blank="Pick your polling station" value={f.registration_centre} options={centres} disabled={!f.ward} onChange={(registration_centre) => setF({ ...f, registration_centre })} />
        </div>
        <VolunteerFields pills value={f} onChange={(patch) => setF((v) => ({ ...v, ...patch }))} />
        <Check className="gap-2.5 text-small leading-[1.5] text-muted-foreground" checked={f.consent_given} onChange={set("consent_given")}>
          {c.consent_wording}
        </Check>
        <ErrorText error={send.error} className="text-small" />
        {!ok ? <p className="text-small text-muted-foreground">Fill in every field, tick at least one way to help and agree above to send this.</p> : null}
        <Button type="submit" disabled={!ok || send.isPending}>{send.isPending ? "Sending…" : "I'll volunteer"}</Button>
      </form>
  );
}

/** The candidate's hero band: photo, seat, name, place and slogan, with `actions` below. */
export function CandidateHero({ c, crumbs, actions }) {
  const where = whereOf(c, ", ");
  return (
    <section className="bg-primary text-white">
      <div className="site-container flex flex-col gap-6 pt-10 pb-12">
        {crumbs ? <Crumbs onDark items={crumbs} /> : null}
        <div className="flex flex-wrap items-center gap-9">
          <Photo url={c.photo_url} className="h-[260px] w-[220px] flex-none rounded-band bg-[#0F7049]" />
          <div className="flex min-w-0 flex-[1_1_400px] flex-col gap-3.5">
            <span className="self-start rounded-full bg-accent px-3 py-1.5 text-small font-extrabold uppercase tracking-[0.08em] text-ink">{vying(c.seat)}</span>
            <h1 className="font-display text-page font-extrabold tracking-[-0.03em]">{c.name}</h1>
            <p className="text-[19px] text-on-primary-muted">{where}{c.slogan ? ` · "${c.slogan}"` : ""}</p>
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
  const first = firstName(c.name);
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
  const state = pageState(query);
  if (state) return state;
  const c = query.data;
  return (
    <CandidateView
      c={c}
      send={send}
      withdrawPath="/candidates/volunteer/withdraw/"
      crumbs={[{ label: "Home", to: "/" }, { label: "Candidates", to: "/candidates" }, { label: c.area }]}
      note={`Profile written from what the candidate sent, and published by the party. ${SEAT_LABEL[c.seat]} aspirant.`}
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
  const first = firstName(c.name);
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
      <Tabs look="underline" value={tab} onValueChange={setTab} className="gap-0">
      <div className="border-b border-line-2 bg-white">
        <TabsList aria-label="Profile sections" className="site-container">
          {tabs.map((t) => <TabsTrigger key={t} value={t}>{t}</TabsTrigger>)}
        </TabsList>
      </div>
      <div className="site-container flex flex-wrap items-start gap-10 pt-12 pb-20">
        <TabsContent value={tab} className="flex min-w-0 flex-[999_1_560px] flex-col gap-4">
          {tab === "About" ? (
            <>
              <RuleHead>About {first}</RuleHead>
              {c.bio ? <RichText html={c.bio} className="text-[18px] leading-[1.7] text-text-2" /> : <p className="text-muted-foreground">The campaign has not sent a biography yet.</p>}
            </>
          ) : null}
          {tab === "Priorities" ? (
            <>
              <RuleHead>Priorities for {c.area}</RuleHead>
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
              <RuleHead>Meet {first}</RuleHead>
              {c.events.length ? c.events.map((e) => (
                <Card key={e.id} asChild interactive className="flex-row flex-wrap items-center justify-between gap-3 p-[18px]">
                  <Link to={`/news/${e.id}`}>
                    <span className="flex flex-col gap-1"><strong className="text-[17px]">{e.title}</strong><span className="text-small text-muted-foreground">{[formatDay(e.event_date, { weekday: "short", day: "numeric", month: "long" }), e.venue].filter(Boolean).join(" · ")}</span></span>
                    <span className="font-bold text-primary">Details →</span>
                  </Link>
                </Card>
              )) : <p className="text-muted-foreground">No party events are planned with {first} yet.</p>}
            </section>
          ) : null}
        </TabsContent>
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
      </Tabs>
      {volunteering ? <VolunteerDialog c={c} send={send} withdrawPath={withdrawPath} onClose={() => setVolunteering(false)} /> : null}
    </>
  );
}
