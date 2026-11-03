// The public page where anyone applies to join the party, in three steps: no login.
import { useState } from "react";
import { useJoinParty, useParty, usePartyPlaces } from "../../api/hooks";
import { Button, ErrorState, FieldLabel, LoadingState } from "../../components/ui";
import { AREAS, CONTACT_METHODS, PROFESSIONS } from "../party/helpers";
import { partyColours } from "./colours";

const STEPS = ["Your details", "Your branch", "Consent"];
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function Field({ label, ...props }) {
  return (
    <>
      <FieldLabel className="join-label join-label-phone">{label}</FieldLabel>
      <input aria-label={label} className="join-field" {...props} />
    </>
  );
}

function PlaceSelect({ label, value, onChange, places, disabled }) {
  return (
    <>
      <FieldLabel className="join-label join-label-phone">{label}</FieldLabel>
      <select
        aria-label={label}
        className="join-field"
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">Pick your {label.toLowerCase()}</option>
        {(places || []).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
      </select>
    </>
  );
}

function Steps({ step }) {
  return (
    <ol className="join-steps" aria-label="Steps">
      {STEPS.map((label, i) => (
        <li key={label} className="join-step" aria-current={step === i + 1 ? "step" : undefined}>
          <span className={`join-step-bar${step >= i + 1 ? " join-step-done" : ""}`} />
          <span className="join-step-label">{i + 1}. {label}</span>
        </li>
      ))}
    </ol>
  );
}

export default function JoinParty() {
  const party = useParty();
  const join = useJoinParty();
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

  const shell = (children) => (
    <div className="join-shell" style={partyColours(party.data)}>
      <div className="join-card">{children}</div>
    </div>
  );

  if (party.isLoading) return shell(<LoadingState className="join-loading" />);
  if (party.error) return shell(<ErrorState className="join-error" error={party.error} />);
  const p = party.data;
  const heading = (
    <div className="party-banner">
      {p.logo_url && <img src={p.logo_url} alt={`${p.name} logo`} className="party-logo" />}
      <div className="join-heading">Become a member of {p.name}</div>
      {p.description && <div className="join-subtitle">{p.description}</div>}
    </div>
  );

  if (join.isSuccess) {
    const link = `${window.location.origin}${join.data.withdraw_url}`;
    const volunteerLink = join.data.volunteer_withdraw_url
      ? `${window.location.origin}${join.data.volunteer_withdraw_url}`
      : "";
    return shell(
      <>
        {heading}
        <div className="join-message-success">
          Thank you, the party has received your application.
        </div>
        <div className="join-note">
          If this number is new to the register, or was rejected or withdrawn before, the
          application will be pending review within a few minutes, and you can sign in with your
          email and password once the party approves it. This link withdraws it:{" "}
          <a href={link} className="join-link">{link}</a> If the number already belongs to an
          application or membership, nothing changes and the link does nothing; contact the party
          instead.
        </div>
        {volunteerLink && (
          <div className="join-note">
            Keep this link too: it stops volunteer contact and leaves your membership as it
            is: <a href={volunteerLink} className="join-link">{volunteerLink}</a>
          </div>
        )}
      </>,
    );
  }

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

  return shell(
    <>
      {heading}
      <Steps step={step} />
      {step === 1 && (
        <>
          <Field label="First name" value={firstName} onChange={(e) => setFirstName(e.target.value)} autoComplete="given-name" />
          <Field label="Surname" value={surname} onChange={(e) => setSurname(e.target.value)} autoComplete="family-name" />
          <Field label="Phone" value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" autoComplete="tel" placeholder="0712 345678" />
          <Field label="Email" value={email} onChange={(e) => setEmail(e.target.value)} type="email" autoComplete="email" />
          <Field label="Password" value={password} onChange={(e) => setPassword(e.target.value)} type="password" autoComplete="new-password" />
          <div className="join-note">At least 8 characters. You sign in with your email and this password once the party approves you.</div>
        </>
      )}
      {step === 2 && (
        <>
          <div className="join-note">Your branch is set by where you are registered to vote.</div>
          <PlaceSelect
            label="County"
            value={county}
            places={counties.data}
            onChange={(v) => { setCounty(v); setConstituency(""); setWard(""); setCentre(""); }}
          />
          <PlaceSelect
            label="Constituency"
            value={constituency}
            places={county ? constituencies.data : []}
            disabled={!county}
            onChange={(v) => { setConstituency(v); setWard(""); setCentre(""); }}
          />
          <PlaceSelect
            label="Ward"
            value={ward}
            places={constituency ? wards.data : []}
            disabled={!constituency}
            onChange={(v) => { setWard(v); setCentre(""); }}
          />
          <PlaceSelect label="Polling station" value={centre} places={ward ? centres.data : []} disabled={!ward} onChange={setCentre} />
          <label className="join-consent">
            <input type="checkbox" checked={volunteer} onChange={(e) => setVolunteer(e.target.checked)} />
            Volunteer for events
          </label>
          {volunteer && (
            <>
              <FieldLabel className="join-label join-label-phone">Profession</FieldLabel>
              <select aria-label="Profession" className="join-field" value={profession} onChange={(e) => setProfession(e.target.value)}>
                <option value="">Pick your profession</option>
                {PROFESSIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
              {profession === "other" && (
                <Field label="Your profession" value={professionOther} maxLength={100} onChange={(e) => setProfessionOther(e.target.value)} />
              )}
              <FieldLabel className="join-label join-label-phone">How would you like to help?</FieldLabel>
              {AREAS.map(([value, label]) => (
                <label key={value} className="join-consent">
                  <input type="checkbox" checked={areas.includes(value)} onChange={() => toggleArea(value)} />
                  {label}
                </label>
              ))}
              {areas.includes("other") && (
                <Field label="Other ways to help" value={areaOther} maxLength={100} onChange={(e) => setAreaOther(e.target.value)} />
              )}
              <FieldLabel className="join-label join-label-phone">Preferred contact</FieldLabel>
              <select aria-label="Preferred contact" className="join-field" value={contact} onChange={(e) => setContact(e.target.value)}>
                <option value="">Pick a contact method</option>
                {CONTACT_METHODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </>
          )}
        </>
      )}
      {step === 3 && (
        <>
          <label className="join-consent">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            {p.consent_wording}
          </label>
          {volunteer && (
            <label className="join-consent">
              <input type="checkbox" checked={volunteerConsent} onChange={(e) => setVolunteerConsent(e.target.checked)} />
              {p.volunteer_consent_wording}
            </label>
          )}
        </>
      )}
      {join.error && <ErrorState className="join-error" error={join.error} />}
      <div className="join-nav">
        {step > 1 ? (
          <Button type="button" onClick={() => setStep(step - 1)}>Back</Button>
        ) : (
          <span />
        )}
        {step < 3 ? (
          <Button type="button" primary disabled={!(step === 1 ? detailsOk : branchOk)} onClick={() => setStep(step + 1)}>
            Continue
          </Button>
        ) : (
          <Button type="button" primary disabled={!consentOk || join.isPending} onClick={send} className="join-submit">
            {join.isPending ? "Sending…" : "Join the party"}
          </Button>
        )}
      </div>
    </>,
  );
}
