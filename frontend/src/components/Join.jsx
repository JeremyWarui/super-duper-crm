// The public page an event's QR code or a campaign's link opens: sign up as a supporter, no login.
import { useState } from "react";
import { useJoin, useJoinPage } from "../api/hooks";

const C = { ink: "#171C1F", paper: "#E9EBE6", panel: "#FFFFFF", green: "#0B6B3A", red: "#B4231F", line: "#D7DBD4", sub: "#5C655F" };
const FIELD = { width: "100%", padding: "12px 14px", borderRadius: 10, border: `1px solid ${C.line}`, fontSize: 16, marginTop: 6, fontFamily: "inherit" };

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
    <div style={{ minHeight: "100vh", background: C.paper, display: "flex", justifyContent: "center", padding: "6vh 16px", fontFamily: "Inter, system-ui, sans-serif", color: C.ink }}>
      <div style={{ background: C.panel, borderRadius: 16, padding: 24, width: "100%", maxWidth: 420, alignSelf: "flex-start" }}>{children}</div>
    </div>
  );

  if (page.isLoading) return shell(<div style={{ color: C.sub }}>Loading…</div>);
  if (page.error) return shell(<div style={{ color: C.red }}>{page.error.message}</div>);
  const p = page.data;
  const heading = (
    <>
      <div style={{ fontSize: 22, fontWeight: 700 }}>{p.campaign_title}</div>
      <div style={{ fontSize: 14, color: C.sub, marginTop: 4 }}>{p.event_title || p.ward_name}{p.candidate_name ? ` · ${p.candidate_name}` : ""}</div>
    </>
  );
  if (join.isSuccess) return shell(<>{heading}<div style={{ marginTop: 20, fontSize: 18, fontWeight: 600, color: C.green }}>{join.data.message}</div><WithdrawNote code={join.data.withdraw_code} /></>);
  if (!p.open) return shell(<>{heading}<div style={{ marginTop: 20, color: C.sub }}>Sign-ups are closed.</div></>);

  return shell(
    <>
      {heading}
      <div style={{ marginTop: 20, fontSize: 13, fontWeight: 600 }}>Full name</div>
      <input aria-label="Full name" style={FIELD} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
      <div style={{ marginTop: 14, fontSize: 13, fontWeight: 600 }}>Phone</div>
      <input aria-label="Phone" style={FIELD} value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" autoComplete="tel" placeholder="0712 345678" />
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
      <label style={{ display: "flex", gap: 8, alignItems: "flex-start", marginTop: 16, fontSize: 13, color: C.sub, cursor: "pointer" }}>
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} style={{ marginTop: 3, accentColor: C.green }} />
        I agree that this campaign may keep my name and phone number to contact me.
      </label>
      {join.error && <div style={{ color: C.red, fontSize: 13, marginTop: 10 }}>{join.error.message}</div>}
      <button disabled={!ok || join.isPending} onClick={() => join.mutate({ full_name: name.trim(), phone: phone.trim(), consent_given: true, place: place || null })}
        style={{ marginTop: 20, width: "100%", padding: "14px", borderRadius: 10, border: "none", fontSize: 16, fontWeight: 600, color: "#fff", background: ok ? C.green : C.line, cursor: ok ? "pointer" : "default" }}>
        {join.isPending ? "Signing up…" : "Sign up"}
      </button>
    </>,
  );
}
