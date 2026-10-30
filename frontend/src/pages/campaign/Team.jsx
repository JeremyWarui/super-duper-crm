import { PageTitle } from "../../components/ui";
import { useTeam } from "../../api/hooks";
import { Btn, Card, ErrorMsg, Loading } from "./controls";
import { ROLE_LABEL } from "./helpers";

// As the API allows: the aspirant resets the manager and mobilizers, the manager resets mobilizers.
const canReset = (role, person) => person.is_active && (person.role === "mobilizer" || (person.role === "manager" && role === "candidate"));

export default function Team({ campaign, role, onModal }) {
  const campaignId = campaign.id;
  const onManager = (sitting) => onModal({ type: "manager", sitting });
  const onReset = (person) => onModal({ type: "reset", person });
  const { data, isLoading, error } = useTeam(campaignId);
  if (isLoading) return <Loading />; if (error) return <ErrorMsg error={error} />;
  const people = data || [];
  const manager = people.find((p) => p.role === "manager");
  const action = role === "candidate" ? <Btn primary onClick={() => onManager(manager)}>{manager ? "Replace manager" : "Add manager"}</Btn> : null;
  return (
    <>
      <PageTitle title="Team" sub="Everyone with a login on this campaign." action={action} />
      <Card pad={0}><div className="table-scroll">
        <table className="table">
          <thead><tr><th>Name</th><th>Username</th><th>Role</th><th/></tr></thead>
          <tbody>{people.map((p) => (<tr key={p.id}><td className="strong">{p.full_name || p.username}</td><td className="muted">{p.username}</td><td>{ROLE_LABEL[p.role]}{!p.is_active && <span className="muted"> · turned off</span>}</td><td className="actions-cell">{canReset(role, p) && <Btn onClick={() => onReset(p)}>Reset password</Btn>}</td></tr>))}</tbody>
        </table>
      </div></Card>
      {!manager && role === "candidate" && <div className="page-note">This campaign has no manager yet. Add one to run the day-to-day.</div>}
    </>
  );
}

