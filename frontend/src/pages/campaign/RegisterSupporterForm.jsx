import { useState } from "react";
import { useAuth } from "../../store/auth";
import { useCentres, useMobilizers, useRegisterSupporter, useTargets } from "../../api/hooks";
import { Btn, Card, Label, PrimaryBtn } from "./controls";

// In an MCA race the supporter is filed to a registration centre with a target, the mobilizer's own to start.
export default function RegisterSupporterForm({ campaignId, wardOptions, byCentre }) {
  const reg = useRegisterSupporter();
  const user = useAuth((s) => s.user);
  const own = (useMobilizers(campaignId).data || []).find((m) => m.user === user?.id);
  const [form, setForm] = useState({ full_name: "", phone: "", ward: "", support_level: "supporter", consent_given: false });
  const ward = form.ward || wardOptions[0]?.id || "";
  const [picked, setPicked] = useState(null);  // null until the centre box is changed
  const centresQuery = useCentres(byCentre ? ward : null);
  const targetsQuery = useTargets(campaignId);
  const targeted = new Set((targetsQuery.data || []).map((t) => t.registration_centre));
  const centres = (centresQuery.data || []).filter((c) => targeted.has(c.id));
  const ownCentre = own?.ward === ward && targeted.has(own?.registration_centre) ? own.registration_centre : null;
  const centre = picked ?? ownCentre ?? "";
  const loaded = !centresQuery.isFetching && !centresQuery.isError && targetsQuery.isSuccess;
  const ok = form.full_name.trim() && form.consent_given && ward && (!byCentre || (loaded && centre));
  if (reg.isSuccess) return <Card pad={20}><div className="success-title">Registered.</div><div className="form-actions"><Btn onClick={() => reg.reset()}>Register another</Btn></div></Card>;
  return (
    <Card pad={20}>
      <Label>Full name</Label><input className="app-field" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
      <div className="field-gap" /><Label>Phone</Label><input className="app-field" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
      <div className="field-gap" /><Label>Ward</Label>
      <select className="app-field" value={ward} onChange={(e) => { setForm({ ...form, ward: e.target.value }); setPicked(null); }}>{wardOptions.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select>
      {byCentre && centres.length > 0 && (
        <>
          <div className="field-gap" /><Label>Registration centre</Label>
          <select aria-label="Registration centre" className="app-field" value={centre} onChange={(e) => setPicked(e.target.value)}>
            <option value="">Pick a centre</option>
            {centres.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </>
      )}
      <div className="field-gap" /><Label>Support</Label>
      <select aria-label="Support" className="app-field" value={form.support_level} onChange={(e) => setForm({ ...form, support_level: e.target.value })}>
        <option value="supporter">Supporter</option>
        <option value="undecided">Undecided</option>
        <option value="opposed">Opposed</option>
      </select>
      <label className="flex items-start gap-2 checkbox-row"><input type="checkbox" checked={form.consent_given} onChange={(e) => setForm({ ...form, consent_given: e.target.checked })} className="checkbox" />Consent to hold these details under the Data Protection Act, 2019.</label>
      {reg.isError && <div className="form-error">{reg.error.message}</div>}
      <div className="form-actions"><PrimaryBtn disabled={!ok || reg.isPending} onClick={() => reg.mutate({ campaign: campaignId, ...form, ward, registration_centre: centre || null })}>{reg.isPending ? "Saving…" : "Register supporter"}</PrimaryBtn></div>
    </Card>
  );
}

