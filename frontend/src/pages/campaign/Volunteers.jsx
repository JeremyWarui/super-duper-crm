// The manager's list of the volunteers the candidate's website page signed up for this campaign.
import { useState } from "react";
import { Badge, Chip, PageTitle } from "../../components/ui";
import { useCampaignVolunteers, useUpdateCampaignVolunteer } from "../../api/hooks";
import { AREA_LABEL, CONTACT_LABEL, PROFESSION_LABEL } from "../party/helpers";
import { Card, ErrorMsg, Loading } from "./controls";

const TONE = { interested: "warn", active: "good", inactive: "bad" };
const FILTERS = ["all", "interested", "active", "inactive"];

function helps(v) {
  return v.interests.map((a) => (a === "other" ? v.interest_other : AREA_LABEL[a])).filter(Boolean).join(", ");
}

export default function Volunteers({ campaign }) {
  const { data, isLoading, error } = useCampaignVolunteers(campaign.id);
  const update = useUpdateCampaignVolunteer(campaign.id);
  const [filter, setFilter] = useState("all");
  const [q, setQ] = useState("");
  if (isLoading) return <Loading />;
  if (error) return <ErrorMsg error={error} />;
  const all = data || [];
  const needle = q.trim().toLowerCase();
  const shown = all.filter((v) => (filter === "all" || v.status === filter) && (!needle || `${v.first_name} ${v.last_name} ${v.phone} ${v.ward.name}`.toLowerCase().includes(needle)));
  return (
    <>
      <PageTitle title="Volunteers" sub={`${all.length} signed up on the candidate's website page`} />
      <div className="flex gap-1 chip-row">
        {FILTERS.map((f) => <Chip key={f} on={filter === f} onClick={() => setFilter(f)} className="chip-capitalize tap">{f}</Chip>)}
        <input type="search" aria-label="Search volunteers" placeholder="Name, phone or ward" className="app-field tap" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <Card pad={0}><div className="table-scroll">
        <table className="table">
          <thead><tr><th>Name</th><th>Phone</th><th>Ward</th><th>Helps with</th><th>Profession</th><th>Contact by</th><th>Status</th><th /></tr></thead>
          <tbody>
            {shown.map((v) => (
              <tr key={v.id}>
                <td className="strong">{v.first_name} {v.last_name}</td>
                <td className="muted">{v.phone}</td>
                <td>{v.ward.name}{v.registration_centre ? <div className="muted">{v.registration_centre.name}</div> : null}</td>
                <td>{helps(v)}</td>
                <td className="muted">{v.profession === "other" ? v.profession_other : PROFESSION_LABEL[v.profession] || "—"}</td>
                <td className="muted">{CONTACT_LABEL[v.preferred_contact]}</td>
                <td><Badge text={v.status} tone={TONE[v.status]} /></td>
                <td>
                  {v.status !== "active" ? (
                    <button type="button" className="link-button tap" disabled={update.isPending} onClick={() => update.mutate({ id: v.id, status: "active" })}>Make active</button>
                  ) : (
                    <button type="button" className="link-button tap" disabled={update.isPending} onClick={() => update.mutate({ id: v.id, status: "inactive" })}>Make inactive</button>
                  )}
                </td>
              </tr>
            ))}
            {update.isError && <tr><td colSpan={8} className="form-error">{update.error.message}</td></tr>}
            {shown.length === 0 && <tr><td colSpan={8} className="empty-row">None yet. Volunteers sign up on the candidate's page on the party website.</td></tr>}
          </tbody>
        </table>
      </div></Card>
    </>
  );
}
