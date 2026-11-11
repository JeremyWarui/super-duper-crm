// /join-party: anyone applies to join the party in three steps, with no login.
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Check as Tick } from "lucide-react";
import { useJoinParty, useParty, useSite } from "@/api/hooks";
import PlaceCascade from "@/components/PlaceCascade";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Check, Field, Input } from "@/components/ui/input";
import { Crumbs } from "@/components/ui/typography";
import VolunteerFields, { CHECK_PILL, NO_VOLUNTEER, volunteerBody, volunteerReady } from "@/components/VolunteerFields";
import { isEmail } from "../../lib/email";
import { ErrorText } from "@/components/ui/error-text";
import { pageState } from "@/components/PageState";
import { linkTo } from "@/lib/format";

const STEPS = ["Your details", "Your branch", "Consent"];

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
      <h1 className="font-display text-page font-extrabold tracking-[-0.03em]">Become a member of {name}</h1>
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
  const [place, setPlace] = useState({ county: "", constituency: "", ward: "", centre: "" });
  const { ward, centre } = place;
  const [smsUpdates, setSmsUpdates] = useState(false);
  const [volunteer, setVolunteer] = useState(false);
  const [vol, setVol] = useState(NO_VOLUNTEER);
  const [consent, setConsent] = useState(false);
  const [volunteerConsent, setVolunteerConsent] = useState(false);

  const detailsOk =
    firstName.trim() && surname.trim() && phone.trim() && isEmail(email) && password.length >= 8;
  const volunteerOk = !volunteer || volunteerReady(vol);
  const branchOk = ward && centre && volunteerOk;
  const consentOk = consent && (!volunteer || volunteerConsent);

  const state = pageState(site, party);
  if (state) return state;
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
        volunteer: { ...volunteerBody(vol), consent_given: true },
      }),
    });

  let body;
  if (join.isSuccess) {
    const link = linkTo(join.data.withdraw_url);
    const volunteerLink = join.data.volunteer_withdraw_url ? linkTo(join.data.volunteer_withdraw_url) : "";
    body = (
      <div className="flex flex-col items-start gap-4 py-3">
        <span className="flex size-14 items-center justify-center rounded-full bg-primary text-white"><Tick className="size-7" strokeWidth={3} /></span>
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
              <PlaceCascade labelled level="centre" place={place} onChange={setPlace} blank={(lv) => (lv === "centre" ? "Pick your polling station" : `Pick your ${lv}`)} />
            </div>
            <label className={`${CHECK_PILL} self-start`}>
              <input type="checkbox" className="size-[18px] accent-primary" checked={volunteer} onChange={(e) => setVolunteer(e.target.checked)} />
              Volunteer for events
            </label>
            {volunteer ? (
              <div className="flex flex-col gap-4 rounded-photo bg-stone p-5">
                <VolunteerFields pills value={vol} onChange={(patch) => setVol((v) => ({ ...v, ...patch }))} />
              </div>
            ) : null}
          </div>
        ) : null}
        {step === 3 ? (
          <div className="flex flex-col gap-[18px]">
            <h2 className="text-[24px] font-bold">Consent</h2>
            <Check className="text-[15px] leading-[1.5]" checked={consent} onChange={(e) => setConsent(e.target.checked)}>
              {p.consent_wording}
            </Check>
            {p.sms_consent_wording ? (
              <Check className="text-[15px] leading-[1.5]" checked={smsUpdates} onChange={(e) => setSmsUpdates(e.target.checked)}>
                <span>{p.sms_consent_wording} <span className="text-muted-foreground">(optional)</span></span>
              </Check>
            ) : null}
            {volunteer ? (
              <Check className="text-[15px] leading-[1.5]" checked={volunteerConsent} onChange={(e) => setVolunteerConsent(e.target.checked)}>
                {p.volunteer_consent_wording}
              </Check>
            ) : null}
          </div>
        ) : null}
        <ErrorText error={join.error} className="text-small" />
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
      <Card className="min-w-0 flex-[1_1_520px] gap-6 self-center rounded-band p-[clamp(20px,4vw,32px)]">{body}</Card>
    </div>
  );
}
