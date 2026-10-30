import { useState } from "react";
import { Badge, Chip, PageTitle } from "../../components/ui";
import { useCentres, usePlaceSupporter, useSupporters, useTargets } from "../../api/hooks";
import { Btn, Card, ErrorMsg, Loading } from "./controls";
import CampaignLinkModal from "./CampaignLinkModal";

export default function Supporters({ campaign, mine }) {
  const campaignId = campaign.id;
  const centreWard = campaign.operational_grain === "centre" ? campaign.ward : null;
  const share = mine ? null : campaign;
  const [sharing, setSharing] = useState(false);
  const { data, isLoading, error } = useSupporters(campaignId);
  const targetsQuery = useTargets(campaignId);
  const targeted = new Set((targetsQuery.data || []).map((t) => t.registration_centre));
  const showCentre = centreWard && targetsQuery.isSuccess;
  const allCentres = useCentres(centreWard).data || [];
  const centres = allCentres.filter((c) => targeted.has(c.id));
  const place = usePlaceSupporter();
  const [filter, setFilter] = useState("all");
  if (isLoading) return <Loading />; if (error) return <ErrorMsg error={error} />;
  const all = data || [];
  const shown = filter === "all" ? all : all.filter((s) => s.support_level === filter);
  const toneOf = { supporter: "good", undecided: "warn", opposed: "bad" };
  return (
    <>
      <PageTitle title="Supporters" sub={`${all.length} on the register`} action={share ? <Btn primary onClick={() => setSharing(true)}>Sign-up link</Btn> : null} />
      <div className="flex gap-1 chip-row">
        {["all", "supporter", "undecided", "opposed"].map((f) => <Chip key={f} on={filter === f} onClick={() => setFilter(f)} className="chip-capitalize">{f}</Chip>)}
      </div>
      <Card pad={0}><div className="table-scroll">
        <table className="table">
          <thead><tr><th>Name</th><th>Phone</th><th>Support</th>{showCentre && <th>Centre</th>}<th>Consent</th></tr></thead>
          <tbody>{shown.map((s) => (<tr key={s.id}><td className="strong">{s.full_name}</td><td className="muted">{s.phone}</td><td><Badge text={s.support_level} tone={toneOf[s.support_level]} /></td>{showCentre && <td>{targeted.has(s.registration_centre)
            ? allCentres.find((c) => c.id === s.registration_centre)?.name || "—"
            : <select aria-label={`Centre for ${s.full_name}`} className="inline-select app-field" value="" disabled={place.isPending} onChange={(e) => place.mutate({ id: s.id, registration_centre: e.target.value })}><option value="">{s.registration_centre ? `${allCentres.find((c) => c.id === s.registration_centre)?.name || "Centre"} has no target` : "Needs a centre"}</option>{centres.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>}</td>}<td>{s.consent_given ? <span className="text-good">✓</span> : <span className="text-bad">missing</span>}</td></tr>))}
          {place.isError && <tr><td colSpan={5} className="form-error">{place.error.message}</td></tr>}
          {shown.length === 0 && <tr><td colSpan={5} className="empty-row">None yet.</td></tr>}</tbody>
        </table>
      </div></Card>
      {sharing && <CampaignLinkModal campaign={share} onClose={() => setSharing(false)} />}
    </>
  );
}

