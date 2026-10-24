// The public page an event's QR code or a campaign's link opens: sign up as a supporter, no login.
import { useState } from "react";
import { useJoin, useJoinPage } from "../api/hooks";
import { Button, ErrorState, FieldLabel, LoadingState } from "./ui";

// The person's own way back off the register; shown once, after signing up.
function WithdrawNote({ code }) {
  const link = `${window.location.origin}/withdraw/${code}`;
  return (
    <div style={{ marginTop: 18, fontSize: 13, color: "#5C655F", lineHeight: 1.5 }}>
      Changed your mind later? Keep this link. Opening it lets you take your details off the
      register: <a href={link} style={{ color: "#0B6B3A", wordBreak: "break-all" }}>{link}</a>
    </div>
  );
}

export default function Join({ code }) {
  const page = useJoinPage(code);
  const join = useJoin(code);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [consent, setConsent] = useState(false);
  const [place, setPlace] = useState("");
  // A campaign's link asks where the person votes: a ward is required, a centre is optional.
  const ok = name.trim() && phone.trim() && consent && (page.data?.place !== "ward" || place);

  const shell = (children) => (
    <div className="join-shell">
      <div className="join-card">{children}</div>
    </div>
  );

  if (page.isLoading) return shell(<LoadingState className="join-loading" />);
  if (page.error) return shell(<ErrorState className="join-error" error={page.error} />);
  const p = page.data;
  const heading = (
    <>
      <div className="join-heading">{p.campaign_title}</div>
      <div className="join-subtitle">{p.event_title || p.ward_name}{p.candidate_name ? ` · ${p.candidate_name}` : ""}</div>
    </>
  );
  if (join.isSuccess) return shell(<>{heading}<div className="join-message-success">{join.data.message}</div><WithdrawNote code={join.data.withdraw_code} /></>);
  if (!p.open) return shell(<>{heading}<div className="join-message-closed">Sign-ups are closed.</div></>);

  return shell(
    <>
      {heading}
      <FieldLabel className="join-label">Full name</FieldLabel>
      <input aria-label="Full name" className="join-field" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
      <FieldLabel className="join-label join-label-phone">Phone</FieldLabel>
      <input aria-label="Phone" className="join-field" value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" autoComplete="tel" placeholder="0712 345678" />
      {p.places.length > 0 && (
        <>
          <div style={{ marginTop: 14, fontSize: 13, fontWeight: 600 }}>{p.place === "centre" ? "Your registration centre" : "Your ward"}</div>
          <select aria-label="Where you vote" value={place} onChange={(e) => setPlace(e.target.value)}
            style={{ width: "100%", padding: "12px 14px", borderRadius: 10, border: "1px solid #D7DBD4", fontSize: 16, marginTop: 6, fontFamily: "inherit", background: "#FFFFFF" }}>
            <option value="">{p.place === "centre" ? "Not sure" : "Pick your ward"}</option>
            {p.places.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        </>
      )}
      <label className="join-consent">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        I agree that this campaign may keep my name and phone number to contact me.
      </label>
      {join.error && <ErrorState className="join-error" error={join.error} />}
      <Button
        type="button"
        disabled={!ok || join.isPending}
        onClick={() => join.mutate({ full_name: name.trim(), phone: phone.trim(), consent_given: true, place: place || null })}
        className={`join-submit ${ok ? "join-submit-enabled" : "join-submit-disabled"}`}
      >
        {join.isPending ? "Signing up…" : "Sign up"}
      </Button>
    </>,
  );
}
