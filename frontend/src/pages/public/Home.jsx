// The party's public home page: no login.
import { Link } from "react-router-dom";
import { useParty } from "../../api/hooks";
import { useAuth } from "../../store/auth";
import { homeOf } from "../../lib/home";
import { partyColours } from "./colours";

export default function Home() {
  const party = useParty().data;
  const token = useAuth((s) => s.token);
  const user = useAuth((s) => s.user);

  return (
    <div className="join-shell" style={partyColours(party)}>
      <div className="join-card">
        {party?.logo_url && <img className="party-logo" src={party.logo_url} alt="" />}
        <div className="join-heading">{party?.name || "Welcome"}</div>
        {party?.description && <div className="join-note">{party.description}</div>}
        <Link className="join-link" to="/join-party">Join the party</Link>
        {token ? (
          <Link className="join-link" to={homeOf(user)}>Portal</Link>
        ) : (
          <Link className="join-link" to="/signin">Sign in</Link>
        )}
      </div>
    </div>
  );
}
