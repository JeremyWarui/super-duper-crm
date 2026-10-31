// The public page where anyone applies to join the party: no login.
import { useState } from "react";
import { useJoinParty, useParty, usePartyPlaces } from "../../api/hooks";
import { Button, ErrorState, FieldLabel, LoadingState } from "../../components/ui";
import { CONTACT_METHODS, INTERESTS } from "../party/helpers";
import { partyColours } from "./colours";

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

export default function JoinParty() {
  const party = useParty();
  const join = useJoinParty();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [county, setCounty] = useState("");
  const [constituency, setConstituency] = useState("");
  const [ward, setWard] = useState("");
  const [consent, setConsent] = useState(false);
  const [volunteer, setVolunteer] = useState(false);
  const [interests, setInterests] = useState([]);
  const [contact, setContact] = useState("");
  const [volunteerConsent, setVolunteerConsent] = useState(false);
  const counties = usePartyPlaces();
  const constituencies = usePartyPlaces({ county, enabled: !!county });
  const wards = usePartyPlaces({ constituency, enabled: !!constituency });
  const volunteerOk = !volunteer || (interests.length > 0 && contact && volunteerConsent);
  const ok = name.trim() && phone.trim() && ward && consent && volunteerOk;
  const toggleInterest = (value) =>
    setInterests((now) => (now.includes(value) ? now.filter((x) => x !== value) : [...now, value]));

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
      <div className="join-heading">{p.name}</div>
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
          application will be pending review within a few minutes, and this link withdraws it:{" "}
          <a href={link} className="join-link">{link}</a> If the number already belongs to an
          application or membership, nothing changes and the link does nothing; contact the party
          instead.
        </div>
        {volunteerLink && (
          <div className="join-note">
            This link stops volunteer contact and leaves your membership as it is:{" "}
            <a href={volunteerLink} className="join-link">Stop volunteer contact</a>
          </div>
        )}
      </>,
    );
  }

  return shell(
    <>
      {heading}
      <FieldLabel className="join-label">Full name</FieldLabel>
      <input aria-label="Full name" className="join-field" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
      <FieldLabel className="join-label join-label-phone">Phone</FieldLabel>
      <input aria-label="Phone" className="join-field" value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" autoComplete="tel" placeholder="0712 345678" />
      <FieldLabel className="join-label join-label-phone">Email (optional)</FieldLabel>
      <input aria-label="Email" className="join-field" value={email} onChange={(e) => setEmail(e.target.value)} type="email" autoComplete="email" />
      <PlaceSelect
        label="County"
        value={county}
        places={counties.data}
        onChange={(v) => { setCounty(v); setConstituency(""); setWard(""); }}
      />
      <PlaceSelect
        label="Constituency"
        value={constituency}
        places={county ? constituencies.data : []}
        disabled={!county}
        onChange={(v) => { setConstituency(v); setWard(""); }}
      />
      <PlaceSelect label="Ward" value={ward} places={constituency ? wards.data : []} disabled={!constituency} onChange={setWard} />
      <label className="join-consent">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        {p.consent_wording}
      </label>
      <label className="join-consent">
        <input type="checkbox" checked={volunteer} onChange={(e) => setVolunteer(e.target.checked)} />
        I would like to volunteer for the party
      </label>
      {volunteer && (
        <>
          {INTERESTS.map(([value, label]) => (
            <label key={value} className="join-consent">
              <input type="checkbox" checked={interests.includes(value)} onChange={() => toggleInterest(value)} />
              {label}
            </label>
          ))}
          <FieldLabel className="join-label join-label-phone">Preferred contact</FieldLabel>
          <select aria-label="Preferred contact" className="join-field" value={contact} onChange={(e) => setContact(e.target.value)}>
            <option value="">Pick a contact method</option>
            {CONTACT_METHODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <label className="join-consent">
            <input type="checkbox" checked={volunteerConsent} onChange={(e) => setVolunteerConsent(e.target.checked)} />
            {p.volunteer_consent_wording}
          </label>
        </>
      )}
      {join.error && <ErrorState className="join-error" error={join.error} />}
      <Button
        type="button"
        disabled={!ok || join.isPending}
        onClick={() =>
          join.mutate({
            full_name: name.trim(),
            phone: phone.trim(),
            email: email.trim() || null,
            ward,
            consent_given: true,
            ...(volunteer && {
              volunteer: { interests, preferred_contact: contact, consent_given: true },
            }),
          })
        }
        primary
        className="join-submit"
      >
        {join.isPending ? "Sending…" : "Join the party"}
      </Button>
    </>,
  );
}
