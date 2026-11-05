import { PageTitle } from "../../components/ui";
import { useTeam } from "../../api/hooks";
import { Btn, Card, ErrorMsg, Loading } from "./controls";
import { ROLE_LABEL } from "./helpers";

// Everyone with a login on the campaign; the candidate and manager add coordinators and comms,
// and set each coordinator's area. Only the candidate adds or replaces the manager.
export default function Team({ campaign, role, onModal }) {
  const { data, isLoading, error } = useTeam(campaign.id);
  if (isLoading) return <Loading />; if (error) return <ErrorMsg error={error} />;
  const people = data || [];
  const manager = people.find((p) => p.role === "manager");
  const actions = (
    <div className="flex flex-wrap gap-2">
      <Btn onClick={() => onModal({ type: "staff", role: "coordinator" })}>Add coordinator</Btn>
      <Btn onClick={() => onModal({ type: "staff", role: "comms" })}>Add comms officer</Btn>
      {role === "candidate" && <Btn primary onClick={() => onModal({ type: "manager", sitting: manager })}>{manager ? "Replace manager" : "Add manager"}</Btn>}
    </div>
  );
  return (
    <>
      <PageTitle title="Team" sub="Everyone with a login on this campaign." action={actions} />
      <Card pad={0}><div className="table-scroll">
        <table className="table">
          <thead><tr><th>Name</th><th>Username</th><th>Role</th><th/></tr></thead>
          <tbody>{people.map((p) => (
            <tr key={p.id}>
              <td className="strong">{p.full_name || p.username}</td>
              <td className="muted">{p.username}</td>
              <td>{ROLE_LABEL[p.role]}{!p.is_active && <span className="muted"> · turned off</span>}</td>
              <td className="actions-cell">{p.role === "coordinator" && <Btn onClick={() => onModal({ type: "area", person: p })} aria-label={`Area for ${p.full_name || p.username}`}>Area</Btn>}</td>
            </tr>
          ))}</tbody>
        </table>
      </div></Card>
      {!manager && role === "candidate" && <div className="page-note">This campaign has no manager yet. Add one to run the day-to-day.</div>}
    </>
  );
}
