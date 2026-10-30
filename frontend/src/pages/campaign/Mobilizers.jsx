import { PageTitle } from "../../components/ui";
import { useMobilizers } from "../../api/hooks";
import { Btn, Card, ErrorMsg, Loading } from "./controls";
import { useUnits } from "./helpers";

export default function Mobilizers({ campaign, onModal }) {
  const campaignId = campaign.id;
  const units = useUnits(campaignId);
  const byCentre = campaign.operational_grain === "centre";
  const onAdd = () => onModal({ type: "mobilizer" });
  const onEdit = (m) => onModal({ type: "mobilizer", mobilizer: m });
  const { data, isLoading, error } = useMobilizers(campaignId);
  if (isLoading) return <Loading />; if (error) return <ErrorMsg error={error} />;
  const placeOf = (m) => {
    if (!byCentre) return m.ward_name;
    if (!m.registration_centre) return null;
    return units.find((u) => u.registration_centre === m.registration_centre)?.name || "A centre with no target";
  };
  return (
    <>
      <PageTitle title="Mobilizers" sub={`Ground organisers by ${byCentre ? "registration centre" : "ward"}.`} action={<Btn primary onClick={onAdd}>Add mobilizer</Btn>} />
      <Card pad={0}><div className="table-scroll">
        <table className="table">
          <thead><tr><th>Name</th><th>{byCentre ? "Centre" : "Ward"}</th><th>Phone</th><th/></tr></thead>
          <tbody>{(data || []).map((m) => (<tr key={m.id}><td className="strong">{m.full_name}</td><td className={placeOf(m) ? undefined : "muted"}>{placeOf(m) || `No ${byCentre ? "centre" : "ward"} yet`}</td><td className="muted">{m.phone || "—"}</td><td className="actions-cell"><Btn onClick={() => onEdit(m)}>Edit</Btn></td></tr>))}
          {(!data || data.length === 0) && <tr><td colSpan={4} className="empty-row">No mobilizers yet.</td></tr>}</tbody>
        </table>
      </div></Card>
    </>
  );
}

