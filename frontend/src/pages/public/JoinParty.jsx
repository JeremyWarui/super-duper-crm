// /join-party: anyone applies to join the party in three steps, with no login.
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Check } from "lucide-react";
import { useJoinParty, useParty, usePartyPlaces, useSite } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, NativeSelect } from "@/components/ui/input";
import { Crumbs } from "@/components/ui/typography";
import { AREAS, CONTACT_METHODS, PROFESSIONS } from "../party/helpers";

const STEPS = ["Your details", "Your branch", "Consent"];
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const TICK = "mt-0.5 size-5 flex-none accent-primary";
const PILL = "flex min-h-11 cursor-pointer items-center gap-2 rounded-full border-[1.5px] border-line-control px-4 font-semibold has-[:checked]:border-primary has-[:checked]:bg-primary-tint";

function PlaceSelect({ label, value, onChange, places, disabled }) {
  return (
    <Field label={label}>
      <NativeSelect value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
        <option value="">Pick your {label.toLowerCase()}</option>
        {(places || []).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
      </NativeSelect>
    </Field>
  );
}

function Steps({ step }) {
  return (
    <ol aria-label="Steps" className="grid grid-cols-3 gap-2">
      {STEPS.map((label, i) => (
        <li key={label} aria-current={step === i + 1 ? "step" : undefined} className="flex flex-col gap-2">
          <span className={`block h-1.5 rounded-full ${step > i ? "bg-primary" : "bg-line-2"}`} />
          <span className={`text-meta font-bold ${step > i ? "text-ink" : "text-muted-foreground"}`}>{i + 1}. {label}</span>
        </li>
      ))}
    </ol>
  );
}

function Intro({ name }) {
  return (
    <div className="flex min-w-0 flex-[1_1_340px] flex-col gap-5">
      <Crumbs items={[{ label: "Home", to: "/" }, { label: "Join the party" }]} />
      <p className="text-ui font-bold uppercase tracking-[0.12em] text-primary">Membership</p>
      <h1 className="font-display text-[clamp(40px,5vw,60px)] leading-none font-extrabold tracking-[-0.03em]">Become a member of {name}</h1>
      <p className="text-[18px] leading-[1.6] text-text-2">Members vote in branch elections and party nominations, and can vie for office.</p>
      <Card className="gap-2.5 p-5 text-[15px]">
        <strong>Before you start, have:</strong>
        <span>• A phone number and an email address</span>
        <span>• The name of the polling station where you are registered to vote</span>
      </Card>
      <p className="text-small leading-[1.6] text-muted-foreground">
        You can be a member of only one registered party. Your details are used to manage your membership, as set out in the <Link to="/privacy">privacy notice</Link>.
      </p>
    </div>
  );
}

export default function JoinParty() {
  const site = useSite();
  const party = useParty();
  const join = useJoinParty();
  // A coordinator's recruitment link adds ?r=; the server ignores a code it does not know.
  const recruitment = useSearchParams()[0].get("r") || undefined;
  const [step, setStep] = useState(1);
  const [firstName, setFirstName] = useState("");
  const [surname, setSurname] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [county, setCounty] = useState("");
  const [constituency, setConstituency] = useState("");
  const [ward, setWard] = useState("");
  const [centre, setCentre] = useState("");
  const [smsUpdates, setSmsUpdates] = useState(false);
  const [volunteer, setVolunteer] = useState(false);
  const [profession, setProfession] = useState("");
  const [professionOther, setProfessionOther] = useState("");
  const [areas, setAreas] = useState([]);
  const [areaOther, setAreaOther] = useState("");
  const [contact, setContact] = useState("");
  const [consent, setConsent] = useState(false);
  const [volunteerConsent, setVolunteerConsent] = useState(false);
  const counties = usePartyPlaces();
  const constituencies = usePartyPlaces({ county, enabled: !!county });
  const wards = usePartyPlaces({ constituency, enabled: !!constituency });
  const centres = usePartyPlaces({ ward, enabled: !!ward });

  const detailsOk =
    firstName.trim() && surname.trim() && phone.trim() && EMAIL.test(email.trim()) && password.length >= 8;
  const volunteerOk =
    !volunteer ||
    (profession &&
      (profession !== "other" || professionOther.trim()) &&
      areas.length > 0 &&
      (!areas.includes("other") || areaOther.trim()) &&
      contact);
  const branchOk = ward && centre && volunteerOk;
  const consentOk = consent && (!volunteer || volunteerConsent);
  const toggleArea = (value) =>
    setAreas((now) => (now.includes(value) ? now.filter((x) => x !== value) : [...now, value]));

  if (site.isLoading || party.isLoading) return <div className="site-container py-12 text-muted-foreground">Loading…</div>;
  const error = site.error || party.error;
  if (error) return <div role="alert" className="site-container py-12">{error.message}</div>;
  const p = { ...site.data, ...party.data };

  const send = () =>
    join.mutate({
      first_name: firstName.trim(),
      surname: surname.trim(),
      phone: phone.trim(),
      email: email.trim(),
      password,
      ward,
      registration_centre: centre,
      consent_given: true,
      sms_updates: smsUpdates,
      ...(recruitment && { recruitment: recruitment.slice(0, 32) }),
      ...(volunteer && {
        volunteer: {
          profession,
          profession_other: profession === "other" ? professionOther.trim() : "",
          areas,
          area_other: areas.includes("other") ? areaOther.trim() : "",
          preferred_contact: contact,
          consent_given: true,
        },
      }),
    });

  let body;
  if (join.isSuccess) {
    const link = `${window.location.origin}${join.data.withdraw_url}`;
    const volunteerLink = join.data.volunteer_withdraw_url ? `${window.location.origin}${join.data.volunteer_withdraw_url}` : "";
    body = (
      <div className="flex flex-col items-start gap-4 py-3">
        <span className="flex size-14 items-center justify-center rounded-full bg-primary text-white"><Check className="size-7" strokeWidth={3} /></span>
        <h2 className="font-display text-[32px] font-extrabold">Karibu! Your application is in.</h2>
        <p role="status" className="leading-[1.6] text-text-2">Thank you, the party has received your application.</p>
        <p className="text-[15px] leading-[1.6] text-text-2">
          If this number is new to the register, or was rejected or withdrawn before, the application will be pending review within a few minutes,
          and you can sign in with your email and password once the party approves it. This link withdraws it:{" "}
          <a href={link} className="break-all font-semibold">{link}</a> If the number already belongs to an application or membership, nothing
          changes and the link does nothing; contact the party instead.
        </p>
        {volunteerLink ? (
          <p className="text-[15px] leading-[1.6] text-text-2">
            Keep this link too: it stops volunteer contact and leaves your membership as it is:{" "}
            <a href={volunteerLink} className="break-all font-semibold">{volunteerLink}</a>
          </p>
        ) : null}
        <div className="flex flex-wrap gap-3 pt-2">
          <Button asChild><Link to="/events">See branch events</Link></Button>
          <Button asChild variant="outline"><Link to="/">Back to home</Link></Button>
        </div>
      </div>
    );
  } else {
    body = (
      <>
        <Steps step={step} />
        {step === 1 ? (
          <div className="flex flex-col gap-[18px]">
            <h2 className="text-[24px] font-bold">Your details</h2>
            <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4">
              <Field label="First name"><Input value={firstName} onChange={(e) => setFirstName(e.target.value)} autoComplete="given-name" /></Field>
              <Field label="Surname"><Input value={surname} onChange={(e) => setSurname(e.target.value)} autoComplete="family-name" /></Field>
              <Field label="Phone"><Input value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" autoComplete="tel" placeholder="07XX XXX XXX" /></Field>
              <Field label="Email"><Input value={email} onChange={(e) => setEmail(e.target.value)} type="email" autoComplete="email" /></Field>
              <Field label="Password">
                <Input value={password} onChange={(e) => setPassword(e.target.value)} type="password" autoComplete="new-password" aria-describedby="pw-hint" />
              </Field>
            </div>
            <p id="pw-hint" className="text-small text-muted-foreground">At least 8 characters. You sign in with your email and this password once the party approves you.</p>
          </div>
        ) : null}
        {step === 2 ? (
          <div className="flex flex-col gap-[18px]">
            <h2 className="text-[24px] font-bold">Where you'll belong</h2>
            <p className="text-muted-foreground">Your branch is set by where you are registered to vote.</p>
            <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4">
              <PlaceSelect label="County" value={county} places={counties.data} onChange={(v) => { setCounty(v); setConstituency(""); setWard(""); setCentre(""); }} />
              <PlaceSelect label="Constituency" value={constituency} places={county ? constituencies.data : []} disabled={!county} onChange={(v) => { setConstituency(v); setWard(""); setCentre(""); }} />
              <PlaceSelect label="Ward" value={ward} places={constituency ? wards.data : []} disabled={!constituency} onChange={(v) => { setWard(v); setCentre(""); }} />
              <PlaceSelect label="Polling station" value={centre} places={ward ? centres.data : []} disabled={!ward} onChange={setCentre} />
            </div>
            <label className={`${PILL} self-start`}>
              <input type="checkbox" className="size-[18px] accent-primary" checked={volunteer} onChange={(e) => setVolunteer(e.target.checked)} />
              Volunteer for events
            </label>
            {volunteer ? (
              <div className="flex flex-col gap-4 rounded-photo bg-stone p-5">
                <Field label="Profession">
                  <NativeSelect value={profession} onChange={(e) => setProfession(e.target.value)}>
                    <option value="">Pick your profession</option>
                    {PROFESSIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </NativeSelect>
                </Field>
                {profession === "other" ? (
                  <Field label="Your profession"><Input value={professionOther} maxLength={100} onChange={(e) => setProfessionOther(e.target.value)} /></Field>
                ) : null}
                <fieldset className="flex flex-col gap-2.5">
                  <legend className="mb-2.5 text-small font-semibold">How would you like to help?</legend>
                  <div className="flex flex-wrap gap-2.5">
                    {AREAS.map(([value, label]) => (
                      <label key={value} className={`${PILL} bg-white text-[15px]`}>
                        <input type="checkbox" className="size-[18px] accent-primary" checked={areas.includes(value)} onChange={() => toggleArea(value)} />
                        {label}
                      </label>
                    ))}
                  </div>
                </fieldset>
                {areas.includes("other") ? (
                  <Field label="Other ways to help"><Input value={areaOther} maxLength={100} onChange={(e) => setAreaOther(e.target.value)} /></Field>
                ) : null}
                <Field label="Preferred contact">
                  <NativeSelect value={contact} onChange={(e) => setContact(e.target.value)}>
                    <option value="">Pick a contact method</option>
                    {CONTACT_METHODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </NativeSelect>
                </Field>
              </div>
            ) : null}
          </div>
        ) : null}
        {step === 3 ? (
          <div className="flex flex-col gap-[18px]">
            <h2 className="text-[24px] font-bold">Consent</h2>
            <label className="flex items-start gap-3 text-[15px] leading-[1.5]">
              <input type="checkbox" className={TICK} checked={consent} onChange={(e) => setConsent(e.target.checked)} />
              {p.consent_wording}
            </label>
            {p.sms_consent_wording ? (
              <label className="flex items-start gap-3 text-[15px] leading-[1.5]">
                <input type="checkbox" className={TICK} checked={smsUpdates} onChange={(e) => setSmsUpdates(e.target.checked)} />
                <span>{p.sms_consent_wording} <span className="text-muted-foreground">(optional)</span></span>
              </label>
            ) : null}
            {volunteer ? (
              <label className="flex items-start gap-3 text-[15px] leading-[1.5]">
                <input type="checkbox" className={TICK} checked={volunteerConsent} onChange={(e) => setVolunteerConsent(e.target.checked)} />
                {p.volunteer_consent_wording}
              </label>
            ) : null}
          </div>
        ) : null}
        {join.error ? <p role="alert" className="text-small font-semibold text-destructive">{join.error.message}</p> : null}
        <div className="flex justify-between gap-3 border-t border-line-soft pt-5">
          {step > 1 ? <Button type="button" variant="quiet" onClick={() => setStep(step - 1)}>Back</Button> : <span />}
          {step < 3 ? (
            <Button type="button" disabled={!(step === 1 ? detailsOk : branchOk)} onClick={() => setStep(step + 1)}>Continue</Button>
          ) : (
            <Button type="button" disabled={!consentOk || join.isPending} onClick={send}>{join.isPending ? "Sending…" : "Join the party"}</Button>
          )}
        </div>
      </>
    );
  }

  return (
    <div className="site-container flex flex-wrap items-start gap-12 pt-12 pb-20">
      <Intro name={p.name} />
      <Card className="min-w-0 flex-[1_1_520px] gap-6 rounded-band p-[clamp(20px,4vw,32px)]">{body}</Card>
    </div>
  );
}
