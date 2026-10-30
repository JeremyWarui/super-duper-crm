import { useAuth } from "../store/auth";

// Only the superuser creates campaigns, so a login on none waits to be put on one.
export default function NoCampaign() {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  return (
    <div className="gate-no-campaign">
      <div className="gate-no-campaign-card">
        <div className="gate-no-campaign-title">
          You are not on a campaign yet
        </div>
        <div className="gate-no-campaign-message">
          You are signed in as {user?.username}, but this login is not on any
          campaign. Ask whoever runs your campaign, or contact support.
        </div>
        <button onClick={logout} className="gate-no-campaign-button">
          Sign out
        </button>
      </div>
    </div>
  );
}
