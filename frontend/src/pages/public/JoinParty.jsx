// The public page where anyone applies to join the party: no login.
import { useState } from "react";
import { useJoinParty, useParty, usePartyPlaces } from "../../api/hooks";
import { Button, ErrorState, FieldLabel, LoadingState } from "../../components/ui";
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
  const counties = usePartyPlaces();
  const constituencies = usePartyPlaces({ county, enabled: !!county });
  const wards = usePartyPlaces({ constituency, enabled: !!constituency });
  const ok = name.trim() && phone.trim() && ward && consent;

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
